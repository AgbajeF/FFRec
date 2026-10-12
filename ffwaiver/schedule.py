"""When to run, and which mode the site is in. All times are US Eastern.

GitHub Actions cron runs in UTC, ignores daylight saving time, and often starts
runs late. So the workflow fires every 30 minutes and `due_job()` works out, in
real Eastern time, which slot is open and hasn't run yet. That handles EDT/EST
automatically and lets a late run catch up instead of missing the slot.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

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


def _slots_on(day):
    """Scheduled slots that start on the ET calendar day of `day`: (start, expires, job)."""
    wd = day.weekday()
    out = []
    if TUE <= wd <= SAT:
        for h in FA_HOURS:
            start = _at(day, time(h, 0))
            out.append((start, start + timedelta(hours=2), "free_agent"))
    if WED <= wd <= SAT or wd == SUN:  # midnight check closing out Tue..Sat
        start = _at(day, time(0, 0))
        end = _at(day, GAME_DAY_TIMES[0]) if wd == SUN else _at(day, time(FA_HOURS[0], 0))
        out.append((start, end, "free_agent"))
    if wd == SUN:
        g1, g2 = (_at(day, t) for t in GAME_DAY_TIMES)
        out.append((g1, g2, "game_day"))
        out.append((g2, _at(day, time(13, 0)), "game_day"))
        out.append((_at(day, PRELIM_TIME), _at(day, FINAL_CHECK_START) + timedelta(days=1), "waiver_prelim"))
    if wd == MON:
        out.append((_at(day, FINAL_CHECK_START), _at(day, time(3, 0)) + timedelta(days=1), "waiver_final_check"))
    return out


def due_job(now, done=()):
    """Return (job, slot_id) for the most recent slot that is still useful and hasn't run yet,
    or (None, None).

    GitHub often starts scheduled runs late (sometimes by hours) and occasionally skips them,
    so the workflow fires frequently and a late run catches up on whatever slot is open.
    `done` holds slot ids that already ran (kept in the Actions cache between runs).
    Jobs: 'waiver_prelim', 'waiver_final_check', 'free_agent', 'game_day'.
    """
    n = to_et(now)
    active = []
    for back in (1, 0):
        for start, end, job in _slots_on(n - timedelta(days=back)):
            if start <= n < end:
                active.append((start, job))
    for start, job in sorted(active, reverse=True):
        slot_id = f"{job}@{start.strftime('%Y-%m-%dT%H:%M')}"
        if slot_id not in done:
            return job, slot_id
    return None, None


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
