"""When to run, and which mode the site is in. All times are US Eastern.

GitHub Actions cron runs in UTC and does not know about daylight saving time,
so the workflow fires at BOTH possible UTC times for every slot (EDT and EST)
and `due_job()` checks the real Eastern time before doing anything. The run
that lands on the wrong side of the DST shift simply finds nothing due and exits.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# How long after a slot's start a (possibly delayed) cron run still counts for it.
# Less than 60 min so the "other DST" hourly run doesn't double up.
SLOT_WINDOW = timedelta(minutes=55)

PRELIM_TIME = time(23, 45)          # Sunday night
FINAL_CHECK_START = time(23, 30)    # Monday night
FINAL_DEADLINE = time(2, 0)         # Tuesday early morning
FA_HOURS = (8, 10, 12, 14, 16, 18, 20, 22)   # Tue-Sat, plus midnight
GAME_DAY_TIMES = (time(10, 0), time(11, 45))  # Sunday


def to_et(dt):
    return dt.astimezone(ET)


def _at(day_dt, t):
    return day_dt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def waiver_deadline(now, waiver_day=TUE, hour=3, minute=0):
    """Next waiver processing time (ET) at or after now."""
    n = to_et(now)
    days_ahead = (waiver_day - n.weekday()) % 7
    cand = (n + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= n:
        cand += timedelta(days=7)
    return cand


def display_mode(now, waiver_day=TUE, waiver_hour=3):
    """Which list is most useful right now: 'waiver', 'free_agent' or 'game_day'."""
    n = to_et(now)
    wd, t = n.weekday(), n.time()
    if wd == SUN and t >= time(23, 30):
        return "waiver"
    if wd == MON:
        return "waiver"
    if wd == waiver_day and t < time(waiver_hour, 0):
        return "waiver"
    if wd == SUN and t >= GAME_DAY_TIMES[0]:
        return "game_day"
    return "free_agent"


def _fa_slots(n):
    """All free-agent check slot datetimes on the ET calendar day of n."""
    wd = n.weekday()
    slots = []
    if TUE <= wd <= SAT:
        slots += [_at(n, time(h, 0)) for h in FA_HOURS]
    if WED <= wd <= SAT or wd == SUN:  # midnight check closing out Tue..Sat
        slots.append(_at(n, time(0, 0)))
    return slots


def due_job(now):
    """Return the scheduled job due at `now`, or None.

    Jobs: 'waiver_prelim', 'waiver_final_check', 'free_agent', 'game_day'.
    """
    n = to_et(now)
    wd, t = n.weekday(), n.time()

    # Sunday-night preliminary list. Window runs into early Monday so a dropped
    # cron can be caught by the next one; duplicates are prevented by the caller
    # (it skips if this week's preliminary list is already published).
    if (wd == SUN and t >= time(23, 30)) or (wd == MON and t < time(6, 0)):
        return "waiver_prelim"

    # Monday 23:30 -> Tuesday ~03:00: poll for "all games final + stats posted".
    if (wd == MON and t >= FINAL_CHECK_START) or (wd == TUE and t < time(3, 0)):
        return "waiver_final_check"

    if wd == SUN:
        for gt in GAME_DAY_TIMES:
            start = _at(n, gt)
            if start <= n < start + SLOT_WINDOW:
                return "game_day"

    for s in _fa_slots(n):
        if s <= n < s + SLOT_WINDOW:
            return "free_agent"
    return None


def final_deadline_passed(now):
    n = to_et(now)
    return n.weekday() == TUE and n.time() >= FINAL_DEADLINE


def fmt_et(dt):
    d = to_et(dt)
    hour = d.strftime("%I").lstrip("0")
    return f"{d.strftime('%a')} {hour}:{d.strftime('%M')} {d.strftime('%p')} ET"


def fmt_clock(dt):
    d = to_et(dt)
    h = d.strftime("%I").lstrip("0")
    return f"{h} {d.strftime('%p')}" if d.minute == 0 else f"{h}:{d.strftime('%M')} {d.strftime('%p')}"
