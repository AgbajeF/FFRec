"""Sleeper OFFICIAL API (documented at https://docs.sleeper.com)."""
import json
import os
import time

from .http import get_json

BASE = "https://api.sleeper.app/v1"

# Fields we keep from the very large /players/nfl response.
PLAYER_FIELDS = (
    "player_id", "full_name", "first_name", "last_name", "position", "fantasy_positions",
    "team", "status", "active", "injury_status", "injury_body_part", "injury_notes",
    "injury_start_date", "practice_participation", "practice_description",
    "depth_chart_position", "depth_chart_order", "news_updated", "espn_id", "gsis_id",
    "search_rank", "years_exp",
)
KEEP_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB", "DE", "DT", "CB", "S", "ILB", "OLB"}


def user(username):
    return get_json(f"{BASE}/user/{username}")


def league(league_id):
    return get_json(f"{BASE}/league/{league_id}")


def rosters(league_id):
    return get_json(f"{BASE}/league/{league_id}/rosters")


def league_users(league_id):
    return get_json(f"{BASE}/league/{league_id}/users")


def transactions(league_id, week):
    return get_json(f"{BASE}/league/{league_id}/transactions/{week}")


def nfl_state():
    return get_json(f"{BASE}/state/nfl")


def trending_adds(lookback_hours=24, limit=50):
    return get_json(f"{BASE}/players/nfl/trending/add",
                    {"lookback_hours": lookback_hours, "limit": limit})


def _slim(players):
    out = {}
    for pid, p in players.items():
        if not isinstance(p, dict):
            continue
        pos = p.get("position")
        if pos not in KEEP_POSITIONS:
            continue
        slim = {k: p.get(k) for k in PLAYER_FIELDS}
        slim["player_id"] = slim.get("player_id") or pid
        out[pid] = slim
    return out


def players(cache_path, max_age_hours=12, force=False):
    """All NFL players. Cached on disk because the response is large (5+ MB).

    Returns (players_dict, fetched_at_epoch, from_cache).
    """
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            age_h = (time.time() - cached["fetched_at"]) / 3600
            if age_h < max_age_hours and cached.get("players"):
                return cached["players"], cached["fetched_at"], True
        except (ValueError, KeyError, OSError):
            pass
    data = _slim(get_json(f"{BASE}/players/nfl", timeout=120))
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    fetched_at = time.time()
    with open(cache_path, "w") as f:
        json.dump({"fetched_at": fetched_at, "players": data}, f)
    return data, fetched_at, False
