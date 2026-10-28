"""Trade analyzer / suggester tests. Run with:  python -m unittest discover tests"""
import os
import tempfile
import unittest
from unittest import mock

from ffwaiver import trades

SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
POS = {}
VALUES = {}


def player(pid, pos, value):
    POS[pid], VALUES[pid] = pos, value
    return pid


# My team: deep at RB, thin at WR. Their team: the opposite.
ME = [player("q1", "QB", 5000), player("r1", "RB", 9000), player("r2", "RB", 7000), player("r3", "RB", 6500),
      player("r4", "RB", 6000), player("w1", "WR", 3000), player("w2", "WR", 1500), player("t1", "TE", 3000)]
THEM = [player("q2", "QB", 5000), player("r5", "RB", 3000), player("r6", "RB", 1500), player("w3", "WR", 9000),
        player("w4", "WR", 7000), player("w5", "WR", 6500), player("w6", "WR", 6000), player("t2", "TE", 3000)]


class TradeMathTests(unittest.TestCase):
    def test_curve_matches_dynastyprocess(self):
        # DynastyProcess lists Ja'Marr Chase at ECR 1.2 with value 10208.
        self.assertEqual(trades.curve(1.2), 10208)

    def test_package_value_prefers_the_stud(self):
        self.assertGreater(trades.package_value(["r1"], VALUES), trades.package_value(["w2", "t1", "w1"], VALUES) * 0.9)
        self.assertLess(trades.package_value(["r2", "r3"], VALUES), 7000 + 6500)

    def test_verdict(self):
        self.assertEqual(trades.verdict(1000, 1050)[1], "Fair trade")
        self.assertEqual(trades.verdict(1000, 2000)[1], "You win this trade")
        self.assertEqual(trades.verdict(2000, 1000)[1], "You'd be overpaying")

    def test_lineup_fills_flex_with_best_leftover(self):
        st = trades.best_lineup(ME, VALUES, POS, SLOTS)
        self.assertEqual(st["r3"], "FLEX")
        self.assertNotIn("r4", st)

    def test_extra_player_forces_a_drop(self):
        new = trades.after_trade(ME, ["r4"], ["w5", "w6"], VALUES, POS, SLOTS)
        self.assertEqual(len(new), len(ME))
        self.assertIn("w5", new)
        self.assertNotIn("w2", new)  # weakest non-starter goes

    def test_swap_from_depth_helps_both(self):
        res = trades.analyze(ME, THEM, ["r4"], ["w6"], VALUES, POS, SLOTS)
        self.assertEqual(res["verdict"], "Fair trade")
        self.assertGreater(res["me"]["delta"], 0)
        self.assertGreater(res["them"]["delta"], 0)
        self.assertIn("w6", res["me"]["new_starters"])


class SuggestTests(unittest.TestCase):
    def test_suggests_rb_for_wr(self):
        players = {pid: {"full_name": pid.upper(), "position": POS[pid]} for pid in POS}
        out = trades.suggest(ME, [(2, "Rival", THEM)], VALUES, POS, SLOTS, players)
        self.assertTrue(out)
        best = out[0]
        self.assertTrue(any(POS[p] == "RB" for p in best["give"]))
        self.assertTrue(all(POS[p] == "WR" for p in best["get"]))
        self.assertGreater(best["my_delta_pct"], 0)
        self.assertGreaterEqual(best["their_delta_pct"], 0)
        self.assertIn("would start for you", best["reason"])

    def test_nothing_when_rosters_match(self):
        players = {pid: {"full_name": pid, "position": POS[pid]} for pid in POS}
        self.assertEqual(trades.suggest(ME, [(2, "Clone", list(ME))], VALUES, POS, SLOTS, players), [])


class ValueSourceTests(unittest.TestCase):
    ECR = ('fp_page,page_type,ecr_type,player,id,pos,team,ecr,tm,scrape_date\n'
           '/x,redraft-overall,ro,Star Back,111,RB,,1,DET,2026-10-23\n'
           '/x,redraft-overall,ro,No Id Guy,999,WR,,20,SEA,2026-10-23\n'
           '/x,redraft-overall,ro,Green Bay Packers,555,DST,,150,GBP,2026-10-23\n'
           '/x,redraft-wr,rp,No Id Guy,999,WR,,5,SEA,2026-10-23\n')
    IDS = "fantasypros_id,sleeper_id,name\n111,4001,Star Back\n"

    def test_redraft_values_map_to_sleeper_ids(self):
        def fake_text(url, *a, **k):
            return self.IDS if url.endswith("db_playerids.csv") else self.ECR
        players = {"4001": {"full_name": "Star Back", "position": "RB"},
                   "4002": {"full_name": "No Id Guy", "position": "WR"},
                   "GB": {"position": "DEF", "team": "GB"}}
        league = {"settings": {"type": 0}, "roster_positions": SLOTS, "scoring_settings": {"rec": 0.5}}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(trades, "get_text", fake_text), \
                mock.patch.object(trades, "fantasycalc_values", side_effect=RuntimeError("down")):
            vals, label, notices = trades.load_values(league, players, os.path.join(d, "ids.json"))
        self.assertEqual(vals["4001"], trades.curve(1))
        self.assertEqual(vals["4002"], trades.curve(20))   # matched by name; overall rank, not the WR rank
        self.assertEqual(vals["GB"], trades.curve(150))     # FantasyPros' GBP -> Sleeper's GB
        self.assertIn("rest-of-season", label)
        self.assertTrue(notices)

    def test_half_ppr_moves_catchers_down_and_runners_up(self):
        # 30 filler players with ordinary ratios, plus a pure pass catcher and a pure runner.
        players, rows, vals = {}, [], {}
        for i in range(30):
            pid = f"f{i}"
            players[pid] = {"gsis_id": f"g{i}"}
            vals[pid] = 5000 - i
            rows += [{"gsis_id": f"g{i}", "fantasy_points": 12.0, "receptions": 3.0}] * 4
        players["catch"], players["run"] = {"gsis_id": "gc"}, {"gsis_id": "gr"}
        vals["catch"], vals["run"] = 4990, 4980
        rows += [{"gsis_id": "gc", "fantasy_points": 6.0, "receptions": 9.0}] * 4
        rows += [{"gsis_id": "gr", "fantasy_points": 14.0, "receptions": 0.0}] * 4
        out, n = trades.scoring_adjust(vals, players, rows, 0.5)
        self.assertEqual(n, 32)
        self.assertEqual(sorted(out.values()), sorted(vals.values()))   # same scale, new order
        self.assertGreater(out["run"], vals["run"])
        self.assertLess(out["catch"], vals["catch"])
        self.assertEqual(trades.scoring_adjust(vals, players, rows, 1), (vals, 0))


if __name__ == "__main__":
    unittest.main()
