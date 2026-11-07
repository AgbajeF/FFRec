"""Start/Sit tests. Run with:  python -m unittest discover tests"""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from ffwaiver import startsit
from ffwaiver.changes import material_changes
from ffwaiver.unofficial_sources import _espn_odds

KO = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
NOW = KO - timedelta(days=2)


def sched(away, home, spread_line, total, roof="", location="Home"):
    return {"week": 10, "kickoff": KO, "away": away, "home": home, "spread_line": spread_line,
            "total_line": total, "roof": roof or None, "location": location, "stadium": ""}


class LineTests(unittest.TestCase):
    def test_nflverse_implied_totals(self):
        # nflverse: spread_line 3 = home team favored by 3.
        lines = startsit.game_lines(10, [sched("KC", "ATL", -3, 46.5)], [])
        self.assertEqual(lines["KC"]["spread"], -3)       # KC favored
        self.assertEqual(lines["ATL"]["spread"], 3)
        self.assertAlmostEqual(lines["KC"]["implied"], 24.75)
        self.assertAlmostEqual(lines["ATL"]["implied"], 21.75)
        self.assertEqual(lines["KC"]["home_away"], "@")
        self.assertEqual(lines["ATL"]["roof"], "retractable")   # filled from the stadium table

    def test_espn_line_wins_over_nflverse(self):
        espn = [{"away": "KC", "home": "ATL", "kickoff": KO,
                 "odds": {"total": 50.0, "home_spread": 2.0, "provider": "ESPN BET"}}]
        lines = startsit.game_lines(10, [sched("KC", "ATL", -3, 46.5)], espn)
        self.assertEqual(lines["ATL"]["total"], 50.0)
        self.assertAlmostEqual(lines["KC"]["implied"], 26.0)
        self.assertEqual(lines["KC"]["source"], "ESPN BET")

    def test_espn_odds_parsing(self):
        comp = {"odds": [{"details": "KC -3.5", "overUnder": 46.5, "provider": {"name": "ESPN BET"}}]}
        o = _espn_odds(comp, {"home": "ATL", "away": "KC"})
        self.assertEqual(o["home_spread"], 3.5)
        self.assertEqual(o["total"], 46.5)
        self.assertEqual(_espn_odds({"odds": [{"details": "EVEN", "overUnder": 40}]}, {"home": "A", "away": "B"})["home_spread"], 0.0)
        self.assertIsNone(_espn_odds({}, {}))
        # ESPN's "WSH" maps to Sleeper's "WAS"
        self.assertEqual(_espn_odds({"odds": [{"details": "WSH -1.5"}]}, {"home": "WAS", "away": "NYG"})["home_spread"], -1.5)


class WeatherTests(unittest.TestCase):
    def test_conditions(self):
        self.assertEqual(startsit.weather_conditions({"wind": 22, "temp": 40}), {"wind", "very_windy"})
        self.assertEqual(startsit.weather_conditions({"wind": 5, "gusts": 30, "temp": 40}), {"wind"})
        self.assertIn("snow", startsit.weather_conditions({"wind": 5, "temp": 30, "precip_prob": 80, "precip": 0.05}))
        self.assertIn("rain", startsit.weather_conditions({"wind": 5, "temp": 55, "precip_prob": 80, "precip": 0.05}))
        self.assertEqual(startsit.weather_conditions({"indoor": True}), set())

    def test_domes_skip_the_forecast(self):
        lines = startsit.game_lines(10, [sched("GB", "DET", 3, 49.5, roof="dome")], [])
        with mock.patch.object(startsit, "forecast") as f:
            w, notice = startsit.weather_for(lines, NOW)
        f.assert_not_called()
        self.assertEqual(w, {"DET": {"indoor": True}})
        self.assertIsNone(notice)

    def test_forecast_reads_mid_game_hour(self):
        hours = [f"2026-11-15T{h:02d}:00" for h in range(24)]
        data = {"hourly": {"time": hours, "temperature_2m": list(range(24)), "wind_speed_10m": [10] * 24,
                           "wind_gusts_10m": [20] * 24, "precipitation_probability": [0] * 24,
                           "precipitation": [0] * 24, "snowfall": [0] * 24}}
        with mock.patch.object(startsit, "get_json", return_value=data):
            w = startsit.forecast(42.7, -78.8, KO)   # 18:00 kickoff -> 19:30 -> 19:00 or 20:00
        self.assertIn(w["temp"], (19.0, 20.0))

    def test_outdoor_far_off_games_not_fetched(self):
        lines = startsit.game_lines(10, [sched("MIA", "BUF", 3, 44)], [])
        with mock.patch.object(startsit, "forecast") as f:
            startsit.weather_for(lines, KO - timedelta(days=9))
        f.assert_not_called()


class AdjustTests(unittest.TestCase):
    def line(self, implied, spread, total, opp_implied=None):
        return {"implied": implied, "spread": spread, "total": total,
                "opp_implied": opp_implied if opp_implied is not None else total - implied}

    def test_high_implied_total_boosts(self):
        hi, _, flags = startsit.adjust("WR", 10, self.line(30, -6, 52), None, 22)
        lo, _, _ = startsit.adjust("WR", 10, self.line(16, 6, 36), None, 22)
        self.assertGreater(hi, 10)
        self.assertLess(lo, 10)
        self.assertTrue(any("Shootout" in f["text"] for f in flags))

    def test_defense_likes_a_weak_opponent(self):
        good, _, _ = startsit.adjust("DEF", 8, self.line(27, -10, 41, opp_implied=14), None, 22)
        bad, _, _ = startsit.adjust("DEF", 8, self.line(18, 6, 48, opp_implied=30), None, 22)
        self.assertGreater(good, 8)
        self.assertLess(bad, 8)

    def test_wind_hurts_kickers_most(self):
        w = {"wind": 24, "temp": 40}
        k, _, flags = startsit.adjust("K", 8, None, w, 22)
        rb, _, _ = startsit.adjust("RB", 8, None, w, 22)
        self.assertLess(k, 7)
        self.assertGreaterEqual(rb, 8)
        self.assertTrue(any(f["text"].startswith("Very windy") for f in flags))

    def test_no_data_no_change(self):
        self.assertEqual(startsit.adjust("WR", 12, None, None, None)[0], 12)


class BuildTests(unittest.TestCase):
    def feat(self, pos, team, proj, injury=None, bye=False, locked=False):
        return {"pos": pos, "team": team, "proj": proj, "recent_avg": proj, "injury": injury, "bye": bye,
                "locked": locked, "kickoff": KO, "home_away": None, "opp_team": None}

    def engine(self, slots):
        def week_value(f):
            return 0.0 if f["bye"] or f["injury"] == "Out" else f["proj"]
        players = {pid: {"first_name": pid.upper(), "last_name": "X", "position": "WR"} for pid in "abcdefgh"}
        return SimpleNamespace(players=players, slots=slots, week_value=week_value)

    def test_vegas_flips_a_close_call_and_tells_me_what_to_change(self):
        lines = startsit.game_lines(10, [sched("KC", "BUF", 2, 53.5), sched("CAR", "NYG", -1, 36.5)], [])
        feats = {"a": self.feat("WR", "KC", 12.0), "b": self.feat("WR", "CAR", 12.4), "c": self.feat("WR", "NYG", 5.0)}
        eng = self.engine(["WR"])
        out = startsit.build(eng, feats, set(), {"starters": ["b"]}, lines, {})
        self.assertEqual(out["lineup"][0]["player_id"], "a")
        self.assertEqual(out["start"], ["A X"])
        self.assertEqual(out["sit"], ["B X"])
        self.assertEqual(out["bench"][0]["player_id"], "b")
        self.assertNotIn("close_call", out["bench"][0])       # 12.9 vs 11.4 isn't close
        self.assertEqual(out["games"][0]["total"], 53.5)       # highest total first
        self.assertEqual(out["games"][0]["mine"], ["A X"])

    def test_locked_starter_stays_and_out_player_sits(self):
        feats = {"a": self.feat("WR", "KC", 5.0, locked=True), "b": self.feat("WR", "CAR", 15.0),
                 "c": self.feat("WR", "NYG", 20.0, injury="Out")}
        out = startsit.build(self.engine(["WR", "FLEX"]), feats, set(), {"starters": ["a", "0"]}, {}, {})
        self.assertEqual([r["player_id"] for r in out["lineup"]], ["a", "b"])
        self.assertEqual(out["empty_slots"], 1)
        self.assertEqual(out["start"], ["B X"])

    def test_close_call(self):
        feats = {"a": self.feat("WR", "KC", 12.0), "b": self.feat("WR", "CAR", 11.5)}
        out = startsit.build(self.engine(["WR"]), feats, set(), {"starters": ["a"]}, {}, {})
        self.assertEqual(out["bench"][0]["close_call"], "Close call with A X (12.0 vs 11.5)")
        self.assertEqual(out["start"], [])

    def test_lineup_change_is_material(self):
        prev = {"picks": [{"player_id": "z", "rank": 1, "name": "Z"}], "start_sit": {"start": [], "sit": []}}
        new = {"picks": prev["picks"], "start_sit": {"start": ["A X"], "sit": ["B X"], "lineup": [
            {"player_id": "a", "name": "A X", "opp": "@ BUF", "flags": [{"text": "Very windy (24 mph)", "kind": "bad"}]}]}}
        reasons = material_changes(new, prev)
        self.assertIn("Your lineup: start A X, bench B X.", reasons)
        self.assertTrue(any("very windy" in r for r in reasons))
        self.assertEqual(material_changes(new, new), [])


if __name__ == "__main__":
    unittest.main()
