"""Trends tab tests. Run with:  python -m unittest discover tests"""
import unittest
from unittest import mock

from ffwaiver import usage

EP_CSV = (
    "season,week,player_id,full_name,position,receptions,receptions_exp,total_fantasy_points,total_fantasy_points_exp\n"
    "2026,1,00-1,Wide Out,WR,6,5,20,14\n"
    "2026,2,00-1,Wide Out,WR,4,5,6,15\n"
)


def week(snap, tgt, car=0, rz=0, team_tgt=30):
    return {"off_snp": snap, "tm_off_snp": 60, "rec_tgt": tgt, "rush_att": car, "rec_rz_tgt": rz,
            "rec": tgt // 2, "gp": 1}


class ExpectedPointsTests(unittest.TestCase):
    def test_moves_full_ppr_to_half_ppr(self):
        with mock.patch.object(usage, "get_text", return_value=EP_CSV):
            ep, notice = usage.expected_points(2026, 0.5)
        self.assertIsNone(notice)
        self.assertEqual(ep[("00-1", 1)], {"x": 11.5, "a": 17.0})   # 14 - 0.5*5, 20 - 0.5*6
        self.assertEqual(ep[("00-1", 2)], {"x": 12.5, "a": 4.0})

    def test_failure_is_a_notice(self):
        with mock.patch.object(usage, "get_text", side_effect=OSError("down")):
            ep, notice = usage.expected_points(2026, 0.5)
        self.assertEqual(ep, {})
        self.assertIn("unavailable", notice)


class LuckTests(unittest.TestCase):
    def test_labels(self):
        cold = [{"x": 15, "a": 10}] * 4
        hot = [{"x": 8, "a": 13}] * 4
        even = [{"x": 12, "a": 13}] * 4
        self.assertEqual(usage.luck(cold, "WR")["label"], "Due for more")
        self.assertEqual(usage.luck(hot, "WR")["label"], "Running hot")
        self.assertEqual(usage.luck(even, "WR")["label"], "On track")
        self.assertEqual(usage.luck(cold[:2], "WR")["label"], "Too early")
        self.assertIsNone(usage.luck([None, None], "WR"))
        self.assertEqual(usage.luck(cold + [None], "WR")["games"], 4)   # missed games don't count

    def test_trend(self):
        self.assertEqual(usage._trend([40, 42, 41, 60, 62])[0], "up")
        self.assertEqual(usage._trend([60, 62, None, 40, 41])[0], "down")
        self.assertEqual(usage._trend([50, 52])[0], "flat")


class BuildTests(unittest.TestCase):
    def test_build(self):
        players = {
            "w1": {"first_name": "Wide", "last_name": "Out", "position": "WR", "team": "KC", "gsis_id": "00-1"},
            "r9": {"first_name": "Run", "last_name": "Ner", "position": "RB", "team": "BUF", "gsis_id": "00-9"},
            "k1": {"first_name": "Kick", "last_name": "Er", "position": "K", "team": "KC"},
        }
        weekly = {w: {"w1": week(10 + 10 * w, 4 + w), "r9": week(45, 3, car=18)} for w in range(1, 6)}
        ep = {("00-1", w): {"x": 10.0, "a": 16.0} for w in range(1, 6)}
        ep.update({("00-9", w): {"x": 15.0, "a": 9.0} for w in range(1, 6)})
        out = usage.build(players, weekly, [], ep, ["w1", "k1"], [(4, "Rival", ["r9"])], {"rec": 0.5, "rec_yd": 0.1})
        self.assertEqual([r["player_id"] for r in out["players"]], ["w1"])   # kickers skipped
        me = out["players"][0]
        self.assertEqual(me["trend"], "up")
        self.assertEqual(me["season"]["label"], "Running hot")
        self.assertEqual(me["weeks"][-1]["snap"], 100)
        self.assertEqual(out["sell_high"][0]["name"], "Wide Out")
        self.assertEqual(out["buy_low"][0]["owner"], "Rival")
        self.assertEqual(out["buy_low"][0]["roster_id"], 4)
        self.assertEqual(out["ep_through"], 5)

    def test_name_match_when_gsis_missing(self):
        players = {"w1": {"first_name": "Wide", "last_name": "Out Jr.", "position": "WR", "team": "KC", "gsis_id": None}}
        weekly = {w: {"w1": week(40, 6)} for w in range(1, 4)}
        rows = [{"gsis_id": "00-1", "name": "Wide Out", "position": "WR", "week": 1, "team": "KC",
                 "target_share": 0.25, "targets": 6, "carries": 0, "air_yards": 80}]
        ep = {("00-1", w): {"x": 10.0, "a": 10.0} for w in range(1, 4)}
        out = usage.build(players, weekly, rows, ep, ["w1"], [], {"rec": 0.5})
        self.assertEqual(out["players"][0]["season"]["games"], 3)
        self.assertEqual(out["players"][0]["weeks"][0]["air"], 80)


if __name__ == "__main__":
    unittest.main()
