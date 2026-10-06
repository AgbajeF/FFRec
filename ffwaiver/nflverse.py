"""nflverse release files (free, public CSVs on GitHub) for multi-week usage trends.

nflverse usually adds a week's data on Monday/Tuesday, so the newest week may be
missing. Callers must treat every function here as optional: each returns
(data, notice) and never raises.
"""
import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .http import get_text

REL = "https://github.com/nflverse/nflverse-data/releases/download"
NFLVERSE_TO_SLEEPER = {"LA": "LAR", "JAC": "JAX", "LVR": "LV", "WSH": "WAS"}
ET = ZoneInfo("America/New_York")


def team(abbr):
    return NFLVERSE_TO_SLEEPER.get(abbr, abbr)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def weekly_player_stats(season):
    """Rows: {gsis_id, week, team, opponent, position, target_share, carries, targets,
    receptions, fantasy_points}. Regular season only."""
    try:
        text = get_text(f"{REL}/stats_player/stats_player_week_{season}.csv")
        rows = []
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("season_type") not in (None, "", "REG"):
                continue
            rows.append({
                "gsis_id": (r.get("player_id") or "").strip(),
                "name": r.get("player_display_name") or r.get("player_name"),
                "week": int(_f(r.get("week"))),
                "team": team(r.get("team") or r.get("recent_team") or ""),
                "opponent": team(r.get("opponent_team") or ""),
                "position": r.get("position"),
                "target_share": _f(r.get("target_share")),
                "carries": _f(r.get("carries")),
                "targets": _f(r.get("targets")),
                "receptions": _f(r.get("receptions")),
                "fantasy_points": _f(r.get("fantasy_points")),
            })
        if not rows:
            raise ValueError("empty")
        return rows, None
    except Exception:
        return [], "Usage trends limited (nflverse data unavailable)."


def schedule(season):
    """Games for the season: {week, kickoff (UTC datetime), home, away, home_score, away_score}.
    Fallback for kickoff times / byes when ESPN is down."""
    try:
        text = get_text(f"{REL}/schedules/games.csv", timeout=120)
        out = []
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("season") != str(season) or r.get("game_type") != "REG":
                continue
            ko = None
            try:
                local = datetime.strptime(f"{r['gameday']} {r.get('gametime') or '13:00'}", "%Y-%m-%d %H:%M")
                ko = local.replace(tzinfo=ET).astimezone(timezone.utc)
            except (ValueError, KeyError):
                pass
            out.append({
                "week": int(_f(r.get("week"))),
                "kickoff": ko,
                "home": team(r.get("home_team")),
                "away": team(r.get("away_team")),
                "home_score": r.get("home_score"),
                "away_score": r.get("away_score"),
            })
        if not out:
            raise ValueError("empty")
        return out, None
    except Exception:
        return [], None


def points_allowed_by_position(rows, rec_points, through_week):
    """{(defense_team, position): avg fantasy points allowed per game} from nflverse rows.
    nflverse fantasy_points is standard scoring; we add the league's per-reception value."""
    totals, games = {}, {}
    for r in rows:
        if r["week"] > through_week or not r["opponent"] or r["position"] not in ("QB", "RB", "WR", "TE"):
            continue
        key = (r["opponent"], r["position"])
        totals[key] = totals.get(key, 0.0) + r["fantasy_points"] + rec_points * r["receptions"]
        games.setdefault(key, set()).add(r["week"])
    return {k: totals[k] / max(1, len(games[k])) for k in totals}
