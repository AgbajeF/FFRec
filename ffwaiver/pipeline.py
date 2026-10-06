"""Fetch everything, run the recommendation engine, and decide whether to publish."""
import json
import os
from datetime import datetime, timedelta, timezone

from . import nflverse, schedule, sleeper_api
from . import unofficial_sources as uo
from .changes import material_changes
from .recommend import player_name, recommend, short_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
PLAYERS_CACHE = os.path.join(ROOT, "state", "cache", "players_nfl.json")

BADGES = {
    "preliminary": {"text": "WAIVER CLAIMS: Preliminary list", "color": "yellow"},
    "final": {"text": "WAIVER CLAIMS: Final list", "color": "green"},
    "free_agent": {"text": "FREE AGENTS: Add anytime", "color": "blue"},
    "game_day": {"text": "GAME DAY: Check before kickoff", "color": "orange"},
}
JOB_MODE = {"waiver_prelim": "waiver", "waiver_final_check": "waiver", "waiver_final": "waiver",
            "free_agent": "free_agent", "game_day": "game_day"}


class Skip(Exception):
    """Nothing to do this run (not an error)."""


def log(msg):
    print(msg, flush=True)


def load_prev():
    path = os.path.join(DOCS, "data.json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _find_my_roster(rosters, user_id, roster_id_cfg):
    if roster_id_cfg not in (None, "", "auto"):
        for r in rosters:
            if str(r.get("roster_id")) == str(roster_id_cfg):
                return r
    for r in rosters:
        if r.get("owner_id") == user_id or user_id in (r.get("co_owners") or []):
            return r
    raise RuntimeError("Couldn't find your team in this league. Check sleeper_username / my_roster_id in config.json.")


def _games_for(week, season, sched_rows, notices):
    games, _, notice = uo.espn_scoreboard(week)
    if games:
        return games, "espn"
    rows = [g for g in sched_rows if g["week"] == week]
    for g in rows:
        g["final"] = g.get("home_score") not in (None, "", "NA")
    if notice and notice not in notices:
        notices.append(notice)
    return rows, "nflverse"


def stats_complete(games, weekly, players):
    """All games final AND the stats endpoint has players for every team that played."""
    if not games:
        return False, "no games found"
    not_final = [f"{g['away']}@{g['home']}" for g in games if not g.get("final")]
    if not_final:
        return False, "not final yet: " + ", ".join(not_final)
    teams = {t for g in games for t in (g.get("home"), g.get("away")) if t}
    counts = {}
    for pid, st in weekly.items():
        p = players.get(pid)
        if p and p.get("team") in teams and ((st.get("off_snp") or 0) > 0 or (st.get("gp") or 0) > 0):
            counts[p["team"]] = counts.get(p["team"], 0) + 1
    missing = sorted(t for t in teams if counts.get(t, 0) < 5)
    if missing:
        return False, "stats not posted yet for: " + ", ".join(missing)
    return True, "complete"


def lock_targets(games_next, now, mode):
    """Countdown targets the page cycles through (first one still in the future wins)."""
    groups = {}
    for g in games_next:
        ko = g.get("kickoff")
        if ko and ko > now:
            groups.setdefault(ko, []).append(g)
    out = []
    for ko in sorted(groups):
        et = schedule.to_et(ko)
        n = len(groups[ko])
        day = schedule.DAY_NAMES[et.weekday()]
        clock = schedule.fmt_clock(ko)
        if et.weekday() == schedule.SUN and (mode == "game_day" or et.date() == schedule.to_et(now).date()):
            label = f"{clock} game{'s' if n > 1 else ''} lock{'' if n > 1 else 's'} in"
        elif et.weekday() == schedule.SUN:
            label = f"Sunday {clock} game{'s' if n > 1 else ''} lock{'' if n > 1 else 's'} in"
        else:
            label = f"{day} game{'s' if n > 1 else ''} lock{'' if n > 1 else 's'} in"
        out.append({"label": label, "iso": ko.isoformat()})
    return out


def build(config, now, job, manual=False, force_publish=False):
    """Returns (data, publish, reasons, notify). Raises Skip when there's nothing to do."""
    notices = []
    mode = JOB_MODE[job]

    # ---- official Sleeper data (required) --------------------------------
    state = sleeper_api.nfl_state()
    season = str(config.get("season") if config.get("season") not in (None, "", "auto") else state.get("season"))
    league = sleeper_api.league(config["league_id"])
    rosters = sleeper_api.rosters(config["league_id"])
    users = sleeper_api.league_users(config["league_id"])
    me_user = sleeper_api.user(config["sleeper_username"])
    my_roster = _find_my_roster(rosters, me_user.get("user_id"), config.get("my_roster_id"))
    rostered = {pid for r in rosters for pid in (r.get("players") or [])}
    team_name = next(((u.get("metadata") or {}).get("team_name") or u.get("display_name")
                      for u in users if u.get("user_id") == my_roster.get("owner_id")), "My team")

    force_players = job == "game_day"
    try:
        players, fetched_at, cached = sleeper_api.players(PLAYERS_CACHE, config["tuning"]["players_cache_hours"], force_players)
    except Exception as e:
        try:
            with open(PLAYERS_CACHE) as f:
                c = json.load(f)
            players, fetched_at, cached = c["players"], c["fetched_at"], True
            notices.append("Player news is from an older snapshot (Sleeper player list unavailable).")
        except Exception:
            raise RuntimeError(f"Sleeper player list unavailable and no cache: {e}")
    log(f"players: {len(players)} ({'cache' if cached else 'fresh'}, fetched {datetime.fromtimestamp(fetched_at, tz=timezone.utc):%Y-%m-%d %H:%M}Z)")

    # ---- which weeks ----------------------------------------------------
    sched_rows, _ = nflverse.schedule(season)
    cur_week = int(state.get("week") or state.get("display_week") or 1)
    cur_games, cur_src = _games_for(cur_week, season, sched_rows, notices)
    any_started = any(g.get("kickoff") and g["kickoff"] <= now for g in cur_games)
    all_final = bool(cur_games) and all(g.get("final") for g in cur_games)
    if mode == "waiver":
        stats_week = cur_week if any_started else cur_week - 1
        next_week = stats_week + 1
    else:
        # Once every game of Sleeper's current week has kicked off, the next lineup is next week's.
        all_started = bool(cur_games) and all(g.get("kickoff") and g["kickoff"] <= now for g in cur_games)
        next_week = cur_week + 1 if (all_final or all_started) else cur_week
        stats_week = next_week - 1
    stats_week = max(1, stats_week)
    games_this = cur_games if stats_week == cur_week else _games_for(stats_week, season, sched_rows, notices)[0]
    games_next = cur_games if next_week == cur_week else _games_for(next_week, season, sched_rows, notices)[0]
    log(f"season {season}: stats week {stats_week}, next week {next_week} (mode {mode}, job {job})")

    # ---- unofficial weekly stats & projections ---------------------------
    weekly = {}
    for w in range(max(1, stats_week - 2), stats_week + 1):
        st, notice = uo.sleeper_weekly_stats(season, w)
        if st:
            weekly[w] = st
        elif notice and w == stats_week:
            notices.append(notice)
    projections, notice = uo.sleeper_projections(season, next_week)
    if notice:
        notices.append(notice)

    # ---- waiver mode: preliminary vs final ------------------------------
    prev = load_prev()
    list_type = {"free_agent": "free_agent", "game_day": "game_day"}.get(mode)
    if mode == "waiver":
        complete, detail = stats_complete(games_this, weekly.get(stats_week, {}), players)
        log(f"week {stats_week} completeness: {detail}")
        same_week = prev and prev.get("week") == next_week
        if job == "waiver_prelim":
            if not manual and same_week and prev.get("list_type") in ("preliminary", "final"):
                raise Skip("preliminary list already published this week")
            list_type = "preliminary"
        elif job == "waiver_final_check":
            if not manual and same_week and prev.get("list_type") == "final":
                raise Skip("final list already published this week")
            if not complete and not schedule.final_deadline_passed(now) and not manual:
                raise Skip(f"waiting for final stats ({detail})")
            list_type = "final" if complete or not manual else "preliminary"
            if list_type == "final" and not complete:
                notices.append("Monday stats may be incomplete: this final list was made at the 2 AM deadline.")
        else:  # explicit "waiver_final" (manual)
            list_type = "final"
            if not complete:
                notices.append(f"Monday stats may be incomplete ({detail}).")

    # ---- nflverse (optional) ---------------------------------------------
    nfl_rows, notice = nflverse.weekly_player_stats(season)
    if notice:
        notices.append(notice)
    pa = nflverse.points_allowed_by_position(nfl_rows, (league.get("scoring_settings") or {}).get("rec", 0), stats_week)

    # Points scored per game by each offense (for DEF / K matchups)
    pts, gms = {}, {}
    for g in sched_rows:
        if g["week"] <= stats_week and g.get("home_score") not in (None, "", "NA"):
            try:
                hs, as_ = float(g["home_score"]), float(g["away_score"])
            except (TypeError, ValueError):
                continue
            for t, s in ((g["home"], hs), (g["away"], as_)):
                pts[t] = pts.get(t, 0) + s
                gms[t] = gms.get(t, 0) + 1
    team_ppg = {t: pts[t] / gms[t] for t in pts}

    # ---- trending, transactions, news ------------------------------------
    try:
        trending = sleeper_api.trending_adds(24, 50)
    except Exception:
        trending = []
        notices.append("Sleeper trending adds unavailable.")
    recent_drops = {}
    for w in {stats_week, next_week}:
        try:
            for tx in sleeper_api.transactions(config["league_id"], w) or []:
                if tx.get("status") != "complete":
                    continue
                t = datetime.fromtimestamp((tx.get("status_updated") or tx.get("created") or 0) / 1000, tz=timezone.utc)
                for pid in (tx.get("drops") or {}):
                    if pid not in rostered and now - t < timedelta(days=7):
                        recent_drops[pid] = max(recent_drops.get(pid, t), t)
        except Exception:
            pass
    injuries, notice = uo.espn_injuries()
    if notice:
        notices.append(notice)
    news, notice = uo.espn_news()
    if notice:
        notices.append(notice)

    waiver_day = schedule.DAY_NAMES.index(config["waivers"]["day"].capitalize())
    deadline = schedule.waiver_deadline(now, waiver_day, config["waivers"]["hour_et"], config["waivers"].get("minute_et", 0))

    ctx = {
        "now": now, "mode": mode, "league": league, "players": players,
        "rostered": rostered, "my_roster": my_roster, "weekly": weekly, "projections": projections,
        "nfl_rows": nfl_rows, "pa_by_pos": pa, "team_ppg": team_ppg, "trending": trending,
        "games_next": games_next, "games_this": games_this, "espn_injuries": injuries, "espn_news": news,
        "recent_drops": recent_drops, "waiver_deadline": deadline, "waiver_hour": config["waivers"]["hour_et"],
        "prev": prev,
        "notices": notices, "list_size": config["tuning"]["list_size"],
        "spike_min": config["tuning"]["trending_spike_min_adds"],
    }
    result = recommend(ctx)

    if mode == "waiver":
        countdown = [{"label": "Waivers run in", "iso": deadline.isoformat()}]
    else:
        countdown = lock_targets(games_next, now, mode)

    data = {
        "generated_at": now.isoformat(),
        "generated_et": schedule.fmt_et(now),
        "mode": mode,
        "list_type": list_type,
        "badge": BADGES[list_type],
        "week": next_week,
        "stats_week": stats_week,
        "season": season,
        "league_name": league.get("name"),
        "team_name": team_name,
        "countdown": countdown,
        "alert": result["alert"],
        "notices": sorted(set(result["notices"]), key=result["notices"].index)[:3],
        "picks": result["picks"],
        "faab": result["faab"],
        "my_roster": [{"player_id": pid, "name": short_name(players.get(pid)),
                       "pos": (players.get(pid) or {}).get("position"),
                       "status": (players.get(pid) or {}).get("injury_status") or ""}
                      for pid in my_roster.get("players") or []],
        "my_roster_status": result["my_roster_status"],
        "my_lineup": result["my_lineup"],
        "site_url": (config.get("site") or {}).get("url") or "",
        "job": job,
    }

    # ---- publish? --------------------------------------------------------
    reasons = material_changes(data, prev if prev and prev.get("week") == next_week else None)
    mode_changed = not prev or prev.get("list_type") != list_type or prev.get("week") != next_week
    urgent = [r for r in reasons if r.startswith(("Your ", "Role opened", "Trending spike"))]
    if list_type in ("preliminary", "final"):
        publish, notify = True, True       # the scheduled waiver lists always publish
        reasons = reasons or [f"{BADGES[list_type]['text']} is ready."]
    elif manual or force_publish:
        publish, notify = True, False
    elif mode_changed:
        # e.g. first free-agent run after waivers clear: refresh the page quietly,
        # but still ping if something urgent happened.
        publish, notify = True, bool(urgent)
    else:
        publish = notify = bool(reasons)
    if not publish:
        raise Skip("no material changes")
    data["change_reasons"] = reasons
    return data, publish, reasons, notify
