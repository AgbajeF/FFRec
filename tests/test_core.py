"""Run with:  python -m unittest discover tests"""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from ffwaiver import schedule
from ffwaiver.changes import material_changes
from ffwaiver.points import fantasy_points

ET = ZoneInfo("America/New_York")


def et(*a):
    return datetime(*a, tzinfo=ET)


class ScheduleTests(unittest.TestCase):
    def job(self, *a, done=()):
        return schedule.due_job(et(*a), done)[0]

    def test_slots_edt_and_est(self):
        # October (EDT) and late November (EST) give the same Eastern-time behavior.
        for month, day in ((10, 4), (11, 29)):  # both Sundays
            self.assertEqual(self.job(2026, month, day, 23, 50), "waiver_prelim")
            self.assertEqual(self.job(2026, month, day, 10, 10), "game_day")
            self.assertEqual(self.job(2026, month, day, 11, 50), "game_day")
            self.assertEqual(self.job(2026, month, day + 1, 23, 35), "waiver_final_check")

    def test_late_runs_catch_up(self):
        # Sunday preliminary list still runs if GitHub starts the run Monday morning.
        self.assertEqual(self.job(2026, 10, 12, 7, 19), "waiver_prelim")
        # Game day check that starts 2 hours late still runs before the 1 PM games.
        self.assertEqual(self.job(2026, 10, 11, 12, 15), "game_day")
        self.assertIsNone(self.job(2026, 10, 11, 14, 30))
        # Thursday 6 PM check delayed to 7:40 PM still runs.
        self.assertEqual(self.job(2026, 10, 8, 19, 40), "free_agent")

    def test_slot_runs_once(self):
        job, slot = schedule.due_job(et(2026, 10, 8, 18, 7))
        self.assertEqual(job, "free_agent")
        self.assertIsNone(self.job(2026, 10, 8, 18, 37, done={slot: 1}))
        self.assertEqual(self.job(2026, 10, 8, 20, 7, done={slot: 1}), "free_agent")
        # The 10 AM game-day slot ran; the 11:45 one is still due.
        g1 = schedule.due_job(et(2026, 10, 11, 10, 7))[1]
        self.assertEqual(self.job(2026, 10, 11, 11, 50, done={g1: 1}), "game_day")

    def test_quiet_times(self):
        self.assertIsNone(self.job(2026, 10, 6, 6, 0))     # Tue before 8 AM
        self.assertIsNone(self.job(2026, 10, 11, 14, 0))   # Sunday afternoon

    def test_display_mode(self):
        self.assertEqual(schedule.display_mode(et(2026, 10, 5, 12, 0)), "waiver")
        self.assertEqual(schedule.display_mode(et(2026, 10, 6, 2, 59)), "waiver")
        self.assertEqual(schedule.display_mode(et(2026, 10, 6, 3, 1)), "free_agent")
        self.assertEqual(schedule.display_mode(et(2026, 10, 11, 10, 30)), "game_day")
        self.assertEqual(schedule.display_mode(et(2026, 10, 11, 23, 40)), "waiver")

    def test_deadline(self):
        self.assertFalse(schedule.final_deadline_passed(et(2026, 10, 6, 1, 59)))
        self.assertTrue(schedule.final_deadline_passed(et(2026, 10, 6, 2, 0)))
        d = schedule.waiver_deadline(et(2026, 10, 5, 22, 0))
        self.assertEqual((d.weekday(), d.hour), (1, 3))


class PointsTests(unittest.TestCase):
    scoring = {"rec": 0.5, "rec_yd": 0.1, "rec_td": 6, "pts_allow_7_13": 4, "sack": 1}

    def test_half_ppr(self):
        self.assertEqual(fantasy_points({"rec": 5, "rec_yd": 60, "rec_td": 1}, self.scoring), 14.5)

    def test_defense_bucket_derived(self):
        self.assertEqual(fantasy_points({"pts_allow": 10, "sack": 3}, self.scoring), 7.0)


class ChangeTests(unittest.TestCase):
    def pick(self, pid, rank, **kw):
        return dict({"player_id": pid, "rank": rank, "name": pid, "pos": "RB", "team": "X"}, **kw)

    def test_small_shuffle_is_quiet(self):
        prev = {"picks": [self.pick(str(i), i) for i in range(1, 21)], "my_roster_status": {}}
        new = {"picks": [self.pick(str(i), i) for i in range(1, 21)], "my_roster_status": {}, "my_roster": []}
        new["picks"][3]["rank"], new["picks"][4]["rank"] = 5, 4   # #4 and #5 swap
        new["picks"][3], new["picks"][4] = new["picks"][4], new["picks"][3]
        self.assertEqual(material_changes(new, prev), [])

    def test_roster_player_ruled_out(self):
        prev = {"picks": [self.pick("1", 1)], "my_roster_status": {"9": "Questionable"}}
        new = {"picks": [self.pick("1", 1)], "my_roster_status": {"9": "Out"},
               "my_roster": [{"player_id": "9", "name": "Star RB"}]}
        self.assertIn("Your Star RB is now Out.", material_changes(new, prev))


if __name__ == "__main__":
    unittest.main()
