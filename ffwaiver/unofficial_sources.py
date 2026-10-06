"""
=============================================================================
 UNOFFICIAL / UNDOCUMENTED ENDPOINTS
=============================================================================
 Everything in this module talks to endpoints that are NOT officially
 documented or supported by their owners. They work today but may change
 shape or disappear without notice:

   Sleeper  /v1/stats/nfl/regular/{season}/{week}        weekly stats
   Sleeper  /v1/projections/nfl/regular/{season}/{week}  weekly projections
   ESPN     site.api.espn.com .../nfl/scoreboard          game status (final?)
   ESPN     site.api.espn.com .../nfl/injuries            injury report
   ESPN     site.api.espn.com .../nfl/news                headlines

 Rules for this module:
   * Every public function returns (data, notice). On any failure or
     unexpected shape, data is an empty value and notice is a short, calm,
     human-readable message for the page. They never raise.
   * Field names were verified against live responses (Oct 2026). Parsing is
     still defensive: unknown or missing fields are skipped, not trusted.
=============================================================================
"""
from datetime import datetime, timezone

from .http import get_json

SLEEPER = "https://api.sleeper.app/v1"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# ESPN uses a few abbreviations that differ from Sleeper's.
ESPN_TO_SLEEPER = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX", "LVR": "LV"}

ESPN_TEAM_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

FINAL_STATES = {"STATUS_FINAL", "STATUS_FINAL_OVERTIME", "STATUS_CANCELED", "STATUS_FORFEIT"}


def norm_team(abbr):
    if not abbr:
        return abbr
    abbr = str(abbr).upper()
    return ESPN_TO_SLEEPER.get(abbr, abbr)


def _parse_iso(s):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        if len(s) == 16 + 6 and s[16] == "+":  # 2026-10-06T00:15+00:00 (no seconds)
            s = s[:16] + ":00" + s[16:]
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# --------------------------------------------------------------------------- Sleeper

def sleeper_weekly_stats(season, week):
    """{player_id: {stat_key: value}} for one regular-season week."""
    try:
        data = get_json(f"{SLEEPER}/stats/nfl/regular/{season}/{week}", timeout=90)
        if isinstance(data, list):  # some seasons return a list of {player_id, stats}
            data = {str(r.get("player_id")): (r.get("stats") or {}) for r in data if isinstance(r, dict)}
        if not isinstance(data, dict):
            raise ValueError("unexpected shape")
        clean = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        if not clean:
            return {}, f"Week {week} stats aren't posted yet."
        return clean, None
    except Exception:
        return {}, f"Week {week} stats unavailable."


def sleeper_projections(season, week):
    try:
        data = get_json(f"{SLEEPER}/projections/nfl/regular/{season}/{week}", timeout=90)
        if isinstance(data, list):
            data = {str(r.get("player_id")): (r.get("stats") or {}) for r in data if isinstance(r, dict)}
        if not isinstance(data, dict) or not data:
            raise ValueError("unexpected shape")
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}, None
    except Exception:
        return {}, "Projections unavailable this week."


# --------------------------------------------------------------------------- ESPN

def espn_scoreboard(week=None, season_type=2):
    """List of games: {id, kickoff (datetime UTC), home, away, state, final, home_score, away_score}.

    Returns (games, week_number_reported_by_espn, notice).
    """
    params = {"seasontype": season_type, "week": week} if week else None
    try:
        data = get_json(f"{ESPN}/scoreboard", params)
        events = data.get("events")
        if not isinstance(events, list):
            raise ValueError("no events")
        games = []
        for ev in events:
            try:
                comp = (ev.get("competitions") or [{}])[0]
                teams = {}
                scores = {}
                for c in comp.get("competitors", []):
                    side = c.get("homeAway")
                    teams[side] = norm_team((c.get("team") or {}).get("abbreviation"))
                    try:
                        scores[side] = int(float(c.get("score") or 0))
                    except (TypeError, ValueError):
                        scores[side] = 0
                st = ((ev.get("status") or comp.get("status") or {}).get("type") or {})
                name = st.get("name") or ""
                games.append({
                    "id": ev.get("id"),
                    "kickoff": _parse_iso(ev.get("date")),
                    "home": teams.get("home"),
                    "away": teams.get("away"),
                    "state": st.get("state"),
                    "status": name,
                    "final": name in FINAL_STATES or (st.get("completed") is True and st.get("state") == "post"),
                    "home_score": scores.get("home", 0),
                    "away_score": scores.get("away", 0),
                })
            except Exception:
                continue
        espn_week = (data.get("week") or {}).get("number")
        if not games:
            raise ValueError("no parsable games")
        return games, espn_week, None
    except Exception:
        return [], None, "Live game status unavailable (ESPN)."


def espn_injuries():
    """List of {name, team, position, status, date, comment}."""
    try:
        data = get_json(f"{ESPN}/injuries")
        teams = data.get("injuries")
        if not isinstance(teams, list):
            raise ValueError("no injuries list")
        out = []
        for t in teams:
            team = ESPN_TEAM_NAMES.get(t.get("displayName")) or norm_team(t.get("abbreviation"))
            for inj in t.get("injuries", []) or []:
                ath = inj.get("athlete") or {}
                out.append({
                    "name": ath.get("displayName"),
                    "team": team,
                    "position": ((ath.get("position") or {}).get("abbreviation")),
                    "status": inj.get("status"),
                    "date": _parse_iso(inj.get("date")),
                    "comment": inj.get("shortComment") or "",
                })
        return out, None
    except Exception:
        return [], "ESPN injury report unavailable."


def espn_news(limit=50):
    """List of {headline, description, published, athlete_ids}."""
    try:
        data = get_json(f"{ESPN}/news", {"limit": limit})
        arts = data.get("articles")
        if not isinstance(arts, list):
            raise ValueError("no articles")
        out = []
        for a in arts:
            ids = []
            for c in a.get("categories", []) or []:
                if c.get("type") == "athlete":
                    aid = c.get("athleteId") or (c.get("athlete") or {}).get("id")
                    if aid:
                        ids.append(str(aid))
            out.append({
                "headline": a.get("headline") or "",
                "description": a.get("description") or "",
                "published": _parse_iso(a.get("published") or a.get("lastModified")),
                "athlete_ids": ids,
            })
        return out, None
    except Exception:
        return [], "ESPN news unavailable."
