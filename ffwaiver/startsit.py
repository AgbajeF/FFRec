"""Start/Sit: Vegas lines, implied team totals and game-day weather for my roster.

Sources (all free, no keys):
  * nflverse schedules (games.csv): spread_line, total_line, roof, stadium. Updated daily.
  * ESPN scoreboard betting line: fresher during the week; used over nflverse when present.
  * Open-Meteo hourly forecast (api.open-meteo.com) at each outdoor stadium near kickoff.

Everything here is optional. With no lines and no weather the tab still ranks the
roster by Sleeper projection, and says the lines are unavailable.
"""
from datetime import timedelta, timezone

from . import schedule
from .http import get_json

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# Home stadium (lat, lon, roof). Roof: "outdoors", "dome" (fixed roof) or "retractable".
# nflverse leaves roof blank for games not yet played, so this is the default.
STADIUMS = {
    "ARI": (33.528, -112.263, "retractable"), "ATL": (33.755, -84.401, "retractable"),
    "BAL": (39.278, -76.623, "outdoors"), "BUF": (42.774, -78.787, "outdoors"),
    "CAR": (35.226, -80.853, "outdoors"), "CHI": (41.862, -87.617, "outdoors"),
    "CIN": (39.095, -84.516, "outdoors"), "CLE": (41.506, -81.700, "outdoors"),
    "DAL": (32.748, -97.093, "retractable"), "DEN": (39.744, -105.020, "outdoors"),
    "DET": (42.340, -83.046, "dome"), "GB": (44.501, -88.062, "outdoors"),
    "HOU": (29.685, -95.411, "retractable"), "IND": (39.760, -86.164, "retractable"),
    "JAX": (30.324, -81.637, "outdoors"), "KC": (39.049, -94.484, "outdoors"),
    "LV": (36.091, -115.184, "dome"), "LAC": (33.953, -118.339, "dome"),
    "LAR": (33.953, -118.339, "dome"), "MIA": (25.958, -80.239, "outdoors"),
    "MIN": (44.974, -93.258, "dome"), "NE": (42.091, -71.264, "outdoors"),
    "NO": (29.951, -90.081, "dome"), "NYG": (40.814, -74.074, "outdoors"),
    "NYJ": (40.814, -74.074, "outdoors"), "PHI": (39.901, -75.168, "outdoors"),
    "PIT": (40.447, -80.016, "outdoors"), "SF": (37.403, -121.970, "outdoors"),
    "SEA": (47.595, -122.332, "outdoors"), "TB": (27.976, -82.503, "outdoors"),
    "TEN": (36.166, -86.771, "outdoors"), "WAS": (38.908, -76.864, "outdoors"),
}
ROOF_WORDS = {"dome": "Dome", "closed": "Roof closed", "retractable": "Retractable roof", "open": "Roof open"}

SHOOTOUT_TOTAL = 48.0
LOW_TOTAL = 40.5
BIG_SPREAD = 7.0
WINDY = 15.0
VERY_WINDY = 20.0


# --------------------------------------------------------------------------- lines

def _r1(x):
    return None if x is None else round(x * 2) / 2   # Vegas lines are in half points


def game_lines(week, sched_rows, espn_games):
    """{team: line} for every team playing `week`.

    line = {opp, home, home_away ("vs"/"@"), kickoff, total, spread (this team's line,
    negative = favored), implied (expected points), opp_implied, roof, neutral, stadium, source}
    """
    espn = {}
    for g in espn_games or []:
        if g.get("home") and g.get("away"):
            espn[(g["away"], g["home"])] = g
    out = {}
    rows = [g for g in sched_rows or [] if g.get("week") == week]
    seen = set()
    for g in rows + [g for g in espn.values()]:
        key = (g.get("away"), g.get("home"))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        away, home = key
        e = espn.get(key) or {}
        odds = e.get("odds") or {}
        nfl = g if "spread_line" in g else next((r for r in rows if (r["away"], r["home"]) == key), {})
        total, home_spread, source = None, None, None
        if odds.get("total") is not None and odds.get("home_spread") is not None:
            total, home_spread, source = odds["total"], odds["home_spread"], odds.get("provider") or "ESPN"
        elif nfl.get("total_line") is not None and nfl.get("spread_line") is not None:
            # nflverse spread_line is the home team's expected margin (positive = home favored).
            total, home_spread, source = nfl["total_line"], -nfl["spread_line"], "nflverse"
        home_imp = away_imp = None
        if total is not None and home_spread is not None:
            home_imp = (total - home_spread) / 2
            away_imp = total - home_imp
        roof = nfl.get("roof") or (STADIUMS.get(home) or (0, 0, None))[2]
        neutral = (nfl.get("location") == "Neutral") or bool(e.get("neutral"))
        kickoff = e.get("kickoff") or nfl.get("kickoff")
        base = {"home": home, "away": away, "kickoff": kickoff, "total": total, "roof": roof,
                "neutral": neutral, "stadium": nfl.get("stadium") or "", "source": source}
        out[home] = dict(base, team=home, opp=away, home_away="vs",
                         spread=home_spread, implied=home_imp, opp_implied=away_imp)
        out[away] = dict(base, team=away, opp=home, home_away="@",
                         spread=None if home_spread is None else -home_spread,
                         implied=away_imp, opp_implied=home_imp)
    return out


# --------------------------------------------------------------------------- weather

def _hour_index(times, target):
    """Index of the hourly slot closest to `target` (times are 'YYYY-MM-DDTHH:MM' in UTC)."""
    want = target.strftime("%Y-%m-%dT%H:00")
    if want in times:
        return times.index(want)
    best, best_i = None, None
    for i, t in enumerate(times):
        d = abs(int(t[11:13]) - target.hour) + (0 if t[:10] == want[:10] else 100)
        if best is None or d < best:
            best, best_i = d, i
    return best_i


def forecast(lat, lon, kickoff):
    """Weather in the middle of the game (kickoff + 90 min), or None."""
    mid = (kickoff + timedelta(minutes=90)).astimezone(timezone.utc)
    day = mid.strftime("%Y-%m-%d")
    try:
        data = get_json(OPEN_METEO, {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,precipitation,snowfall,wind_speed_10m,wind_gusts_10m",
            "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch",
            "timezone": "UTC", "start_date": day, "end_date": day,
        }, timeout=20, retries=1)
        h = data["hourly"]
        i = _hour_index(h["time"], mid)
        if i is None:
            return None

        def val(k):
            v = (h.get(k) or [None] * (i + 1))[i]
            return float(v) if v is not None else None
        return {"temp": val("temperature_2m"), "precip_prob": val("precipitation_probability"),
                "precip": val("precipitation"), "snow": val("snowfall"),
                "wind": val("wind_speed_10m"), "gusts": val("wind_gusts_10m")}
    except Exception:
        return None


def weather_for(lines, now, max_days=7):
    """{home_team: weather} for outdoor (and retractable-roof) games within `max_days`.
    Domes get {"indoor": True}. Returns (weather, notice)."""
    out, tried, failed = {}, 0, 0
    for home, ln in lines.items():
        if ln["home_away"] != "vs":
            continue
        roof = ln.get("roof")
        if roof in ("dome", "closed"):
            out[home] = {"indoor": True}
            continue
        ko = ln.get("kickoff")
        if ln.get("neutral") or not ko or ko < now - timedelta(hours=4) or ko > now + timedelta(days=max_days):
            continue
        st = STADIUMS.get(home)
        if not st:
            continue
        tried += 1
        w = forecast(st[0], st[1], ko)
        if w:
            w["roof"] = roof
            out[home] = w
        else:
            failed += 1
    notice = "Weather forecast unavailable right now (Open-Meteo)." if tried and failed == tried else None
    return out, notice


def weather_conditions(w):
    """Set of {"wind", "very_windy", "rain", "snow", "cold"} for an outdoor forecast."""
    if not w or w.get("indoor"):
        return set()
    c = set()
    wind = max(w.get("wind") or 0, (w.get("gusts") or 0) * 0.6)
    if wind >= VERY_WINDY:
        c |= {"wind", "very_windy"}
    elif wind >= WINDY:
        c.add("wind")
    wet = (w.get("precip_prob") or 0) >= 50 and (w.get("precip") or 0) >= 0.02
    if wet and ((w.get("snow") or 0) > 0 or (w.get("temp") or 50) <= 33):
        c.add("snow")
    elif wet:
        c.add("rain")
    if w.get("temp") is not None and w["temp"] <= 25:
        c.add("cold")
    return c


def weather_text(w, roof=None):
    if not w:
        return None
    if w.get("indoor"):
        return ROOF_WORDS.get(roof, "Dome") + ", no weather"
    bits = []
    if w.get("temp") is not None:
        bits.append(f"{round(w['temp'])}°F")
    if w.get("wind") is not None:
        bits.append(f"wind {round(w['wind'])} mph" + (f" (gusts {round(w['gusts'])})" if (w.get("gusts") or 0) >= 25 else ""))
    if (w.get("precip_prob") or 0) >= 30:
        kind = "snow" if "snow" in weather_conditions(w) else "rain"
        bits.append(f"{round(w['precip_prob'])}% {kind}")
    txt = ", ".join(bits)
    if roof == "retractable":
        txt += " (retractable roof, may be closed)"
    return txt or None


# --------------------------------------------------------------------------- adjustments

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def adjust(pos, proj, line, w, avg_implied):
    """(adjusted projection, multiplier, flags) for one player.

    Sleeper projections already price in some of the matchup, so Vegas moves them only
    modestly: a team implied for 10% more than the week's average gets about +5%.
    """
    flags = []
    m = 1.0
    if line and line.get("implied") is not None and avg_implied:
        imp, spread, total = line["implied"], line["spread"], line["total"]
        if pos == "DEF":
            m *= _clamp(1 + 0.8 * (1 - line["opp_implied"] / avg_implied), 0.80, 1.25)
        else:
            m *= _clamp(1 + 0.5 * (imp / avg_implied - 1), 0.85, 1.15)
        fav_by = -spread
        if pos == "RB":
            m *= 1 + _clamp(0.008 * fav_by, -0.05, 0.05)        # leading teams run the ball
        elif pos in ("WR", "TE") and fav_by <= -BIG_SPREAD:
            m *= 1.03                                           # trailing teams throw late
        if total >= SHOOTOUT_TOTAL and pos != "DEF":
            flags.append({"text": "Shootout", "kind": "good"})
        elif total <= LOW_TOTAL:
            flags.append({"text": "Low total", "kind": "good" if pos == "DEF" else "bad"})
        if fav_by >= BIG_SPREAD:
            flags.append({"text": "Big favorite", "kind": "good" if pos in ("RB", "DEF", "K") else ""})
        elif fav_by <= -BIG_SPREAD:
            flags.append({"text": "Big underdog", "kind": "bad" if pos in ("RB", "DEF") else ""})
    cond = weather_conditions(w)
    wx = {"K": {"wind": .88, "very_windy": .89, "snow": .90, "rain": .95},
          "QB": {"wind": .96, "very_windy": .94, "snow": .93, "rain": .96},
          "WR": {"wind": .96, "very_windy": .94, "snow": .93, "rain": .96},
          "TE": {"wind": .97, "very_windy": .96, "snow": .95, "rain": .97},
          "RB": {"very_windy": 1.02, "snow": 1.02},
          "DEF": {"very_windy": 1.04, "snow": 1.04, "rain": 1.03}}.get(pos, {})
    for c in cond:
        m *= wx.get(c, 1.0)
    if "very_windy" in cond:
        flags.append({"text": f"Very windy ({round(w['wind'])} mph)", "kind": "bad" if pos in ("K", "QB", "WR", "TE") else ""})
    elif "wind" in cond:
        flags.append({"text": f"Windy ({round(max(w['wind'] or 0, (w.get('gusts') or 0) * 0.6))} mph)",
                      "kind": "bad" if pos in ("K", "QB", "WR") else ""})
    if "snow" in cond:
        flags.append({"text": "Snow", "kind": "bad" if pos in ("K", "QB", "WR", "TE") else ""})
    elif "rain" in cond:
        flags.append({"text": "Rain", "kind": "bad" if pos in ("K", "QB", "WR") else ""})
    if "cold" in cond:
        flags.append({"text": f"Cold ({round(w['temp'])}°F)", "kind": ""})
    if w and w.get("indoor") and pos in ("K", "QB", "WR"):
        flags.append({"text": "Dome", "kind": "good"})
    m = _clamp(m, 0.70, 1.30)
    return proj * m, m, flags


# --------------------------------------------------------------------------- build

def _spread_text(ln):
    if ln.get("spread") is None:
        return None
    s = ln["spread"]
    if s == 0:
        return "Pick'em"
    fav = ln["team"] if s < 0 else ln["opp"]
    return f"{fav} -{abs(s):g}"


def build(engine, my_feats, reserve, my_roster, lines, weather, notices=None):
    """The Start/Sit section of the page data. `engine` is recommend.Engine."""
    from .recommend import SLOT_ELIG, OUT_STATUSES, short_name   # avoid a circular import

    players = engine.players
    implied = [ln["implied"] for ln in lines.values() if ln.get("implied") is not None]
    avg_implied = sum(implied) / len(implied) if implied else None
    implied_rank = {t: i + 1 for i, t in enumerate(sorted(
        (t for t, ln in lines.items() if ln.get("implied") is not None), key=lambda t: -lines[t]["implied"]))}

    rows = {}
    for pid, f in my_feats.items():
        if pid in reserve:
            continue
        team = f["team"]
        ln = lines.get(team)
        w = weather.get(ln["home"]) if ln else None
        base = engine.week_value(f)
        adj, mult, flags = adjust(f["pos"], base, ln, w, avg_implied)
        if f["bye"]:
            flags = [{"text": "Bye week", "kind": "bad"}]
        elif f["injury"] in OUT_STATUSES:
            flags = [{"text": f["injury"], "kind": "bad"}]
        elif f["injury"] in ("Questionable", "Doubtful"):
            flags.insert(0, {"text": f["injury"], "kind": "bad"})
        ko = (ln or {}).get("kickoff") or f.get("kickoff")
        rows[pid] = {
            "player_id": pid, "name": short_name(players.get(pid)), "pos": f["pos"], "team": team,
            "opp": f"{ln['home_away']} {ln['opp']}" if ln else (f"{f['home_away']} {f['opp_team']}" if f.get("opp_team") else None),
            "kickoff_et": schedule.fmt_et(ko) if ko else None,
            "proj": round(base, 1), "adj": round(adj, 1), "delta": round(adj - base, 1),
            "total": _r1((ln or {}).get("total")), "spread": _spread_text(ln) if ln else None,
            "implied": round(ln["implied"], 1) if ln and ln.get("implied") is not None else None,
            "implied_rank": implied_rank.get(team),
            "weather": weather_text(w, (ln or {}).get("roof")),
            "flags": flags, "injury": f["injury"] or "", "locked": bool(f.get("locked")), "bye": bool(f["bye"]),
            "_v": adj,
        }

    # Recommended lineup: most restrictive slots first, highest adjusted projection wins.
    # A player whose game has kicked off can't be moved: keep locked starters where they are
    # and never suggest starting a locked bench player.
    slots = engine.slots
    order = sorted(range(len(slots)), key=lambda i: len(SLOT_ELIG[slots[i]]))
    used, lineup = set(), [None] * len(slots)
    cur_slots = list(my_roster.get("starters") or [])
    if len(cur_slots) == len(slots):
        for i, pid in enumerate(cur_slots):
            if pid in rows and rows[pid]["locked"]:
                used.add(pid)
                lineup[i] = (slots[i], pid)
    locked_bench = {pid for pid, r in rows.items() if r["locked"] and pid not in used}
    for i in order:
        if lineup[i]:
            continue
        best = None
        for pid, r in rows.items():
            if pid in used or pid in locked_bench or r["pos"] not in SLOT_ELIG[slots[i]] or r["_v"] <= 0:
                continue
            if best is None or r["_v"] > rows[best]["_v"]:
                best = pid
        if best:
            used.add(best)
        lineup[i] = (slots[i], best)

    starters = []
    for slot, pid in lineup:
        r = dict(rows[pid]) if pid else {"name": None}
        r["slot"] = slot
        starters.append(r)
    bench = sorted((rows[pid] for pid in rows if pid not in used), key=lambda r: -r["_v"])

    # Close calls: a bench player within ~1 point (or 8%) of the starter he could replace.
    for b in bench:
        if b["_v"] <= 0 or b["locked"]:
            continue
        cands = [s for s in starters if s.get("player_id") and not s["locked"] and b["pos"] in SLOT_ELIG[s["slot"]]]
        if not cands:
            continue
        s = min(cands, key=lambda s: s["_v"])
        if b["_v"] >= s["_v"] - max(1.0, 0.08 * s["_v"]):
            b["close_call"] = f"Close call with {s['name']} ({s['adj']} vs {b['adj']})"
            s.setdefault("close_with", []).append(b["name"])

    # Compare to the lineup currently set in Sleeper.
    current = [p for p in (my_roster.get("starters") or []) if p and p != "0"]
    rec = [pid for _, pid in lineup if pid]
    start = [rows[p]["name"] for p in rec if p not in current and not rows[p]["locked"]]
    sit = [rows[p]["name"] if p in rows else short_name(players.get(p)) for p in current
           if p not in rec and not (rows.get(p) or {}).get("locked")]
    empty = sum(1 for p in (my_roster.get("starters") or []) if p in (None, "", "0"))

    for r in starters + bench:
        r.pop("_v", None)

    games = []
    mine_by_team = {}
    for pid in rows:
        mine_by_team.setdefault(rows[pid]["team"], []).append(rows[pid]["name"])
    for home, ln in lines.items():
        if ln["home_away"] != "vs":
            continue
        away = lines.get(ln["opp"]) or {}
        w = weather.get(home)
        games.append({
            "away": ln["opp"], "home": home, "kickoff_et": schedule.fmt_et(ln["kickoff"]) if ln.get("kickoff") else None,
            "total": _r1(ln.get("total")), "spread": _spread_text(ln),
            "away_implied": round(away["implied"], 1) if away.get("implied") is not None else None,
            "home_implied": round(ln["implied"], 1) if ln.get("implied") is not None else None,
            "weather": weather_text(w, ln.get("roof")) if w else (ROOF_WORDS.get(ln.get("roof")) if ln.get("roof") in ("dome", "closed") else None),
            "weather_flags": sorted(weather_conditions(w)),
            "mine": mine_by_team.get(ln["opp"], []) + mine_by_team.get(home, []),
        })
    games.sort(key=lambda g: (-(g["total"] or 0), g["kickoff_et"] or ""))

    sources = sorted({ln["source"] for ln in lines.values() if ln.get("source")})
    return {
        "lineup": starters,
        "bench": bench,
        "start": start, "sit": sit, "empty_slots": empty,
        "games": games,
        "avg_implied": round(avg_implied, 1) if avg_implied else None,
        "lines_source": ", ".join(sources) if sources else None,
        "has_weather": any(not w.get("indoor") for w in weather.values()),
    }
