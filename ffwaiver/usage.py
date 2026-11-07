"""Trends tab: week-by-week usage for my players, and expected vs actual fantasy points.

Sources (free, no keys):
  * Sleeper weekly stats (already fetched): snaps, targets, carries, red-zone looks, points.
  * nflverse weekly player stats: target share, air yards, air-yards share.
  * ffverse "ffopportunity" expected points (github.com/ffverse/ffopportunity, the model
    behind nflverse's ff_opportunity data): how many points a player's targets and carries
    were worth on average, given where on the field and how far downfield they came.

"Expected" points say how good a player's opportunity was; the gap to his actual points is
mostly touchdown and big-play luck, which tends to even out. A player well below his expected
points is a buy-low or hold; one well above is running hot and worth selling high.
"""
import csv
import io

from .http import get_text
from .points import fantasy_points, played

EP_URL = "https://github.com/ffverse/ffopportunity/releases/download/latest-data/ep_weekly_{season}.csv"
SKILL = ("QB", "RB", "WR", "TE")
WEEKS_SHOWN = 6
MIN_GAMES = 3
# Per-game gap (actual - expected) that counts as luck, by position.
LUCK_GAP = {"QB": 3.5, "RB": 2.5, "WR": 2.5, "TE": 2.0}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def expected_points(season, rec_pts):
    """{(gsis_id, week): {"x": expected, "a": actual}} in the league's reception scoring.

    ffopportunity scores full PPR, so both numbers are moved to the league's points per
    reception (expected receptions for the expected side). Returns (data, notice)."""
    try:
        text = get_text(EP_URL.format(season=season), timeout=90)
        out = {}
        for r in csv.DictReader(io.StringIO(text)):
            gid = (r.get("player_id") or "").strip()
            if not gid:
                continue
            adj = 1.0 - (rec_pts or 0)
            x = _f(r.get("total_fantasy_points_exp")) - adj * _f(r.get("receptions_exp"))
            a = _f(r.get("total_fantasy_points")) - adj * _f(r.get("receptions"))
            out[(gid, int(_f(r.get("week"))))] = {"x": round(x, 1), "a": round(a, 1)}
        if not out:
            raise ValueError("empty")
        return out, None
    except Exception:
        return {}, "Expected points unavailable right now (ffopportunity)."


def luck(games, pos):
    """Season summary and a buy/sell label from per-week {"x", "a"} rows."""
    games = [g for g in games if g]
    if not games:
        return None
    n = len(games)
    x = sum(g["x"] for g in games) / n
    a = sum(g["a"] for g in games) / n
    diff = a - x
    gap = LUCK_GAP.get(pos, 2.5)
    out = {"games": n, "xpts": round(x, 1), "pts": round(a, 1), "diff": round(diff, 1)}
    if n < MIN_GAMES:
        out.update(label="Too early", kind="", text=f"Only {n} game{'s' if n > 1 else ''} of data so far.")
    elif diff <= -gap:
        out.update(label="Due for more", kind="good",
                   text=f"Scoring {abs(diff):.1f} fewer points a game than his usage is worth. Hold, or buy low.")
    elif diff >= gap:
        out.update(label="Running hot", kind="bad",
                   text=f"Scoring {diff:.1f} more points a game than his usage is worth. Likely to cool off: sell high.")
    else:
        out.update(label="On track", kind="", text="Scoring about what his usage is worth.")
    return out


def _trend(scores):
    """'up' / 'down' / 'flat' from weekly usage scores (None = didn't play)."""
    vals = [s for s in scores if s is not None]
    if len(vals) < 3:
        return "flat", 0.0
    recent = sum(vals[-2:]) / 2
    before = sum(vals[:-2]) / len(vals[:-2])
    d = recent - before
    return ("up" if d >= 8 else "down" if d <= -8 else "flat"), round(d, 1)


def build(players, weekly, nfl_rows, ep, my_pids, other_teams, scoring):
    """The Trends section of the page data.

    weekly: {week: {pid: stats}}
    from Sleeper. other_teams: [(roster_id, team name, [pids])] for the rest of the league.
    """
    from .recommend import short_name, usage_score   # avoid a circular import

    weeks = sorted(weekly)[-WEEKS_SHOWN:]
    nfl = {}
    for r in nfl_rows or []:
        if r.get("gsis_id"):
            nfl[(r["gsis_id"], r["week"])] = r
    team_tgt, team_car = {}, {}
    for w in weeks:
        tt, tc = {}, {}
        for pid, st in weekly[w].items():
            t = (players.get(pid) or {}).get("team")
            if t and (players.get(pid) or {}).get("position") != "DEF":
                tt[t] = tt.get(t, 0) + (st.get("rec_tgt") or 0)
                tc[t] = tc.get(t, 0) + (st.get("rush_att") or 0)
        team_tgt[w], team_car[w] = tt, tc
    ep_weeks = sorted({w for _, w in ep})

    def pos_of(pid):
        p = players.get(pid) or {}
        pos = p.get("position")
        return pos if pos in SKILL else None

    def season_luck(pid):
        gsis = ((players.get(pid) or {}).get("gsis_id") or "").strip()
        return luck([ep.get((gsis, w)) for w in ep_weeks], pos_of(pid)) if gsis else None

    rows = []
    for pid in my_pids:
        pos = pos_of(pid)
        if not pos:
            continue
        p = players[pid]
        gsis = (p.get("gsis_id") or "").strip()
        wk_rows, scores = [], []
        for w in weeks:
            st = weekly[w].get(pid) or {}
            nv = nfl.get((gsis, w)) or {}
            e = ep.get((gsis, w))
            if not played(st) and not nv:
                wk_rows.append({"week": w, "played": False})
                scores.append(None)
                continue
            team = p.get("team")
            snap = (st.get("off_snp") or 0) / st["tm_off_snp"] if st.get("tm_off_snp") else None
            tgt = st.get("rec_tgt") or nv.get("targets") or 0
            car = st.get("rush_att") or nv.get("carries") or 0
            tshare = nv.get("target_share") or ((tgt / team_tgt[w][team]) if team_tgt[w].get(team) else None)
            cshare = (car / team_car[w][team]) if team_car[w].get(team) else None
            rz = (st.get("rec_rz_tgt") or 0) + (st.get("rush_rz_att") or 0)
            row = {"week": w, "played": True, "pts": round(fantasy_points(st, scoring), 1),
                   "xpts": e["x"] if e else None,
                   "snap": round(snap * 100) if snap is not None else None,
                   "tgt": int(tgt), "tgt_share": round(tshare * 100) if tshare else None,
                   "air": int(nv.get("air_yards") or 0) if nv else None,
                   "car": int(car), "car_share": round(cshare * 100) if cshare else None, "rz": int(rz)}
            wk_rows.append(row)
            scores.append(usage_score(pos, {
                "played": True, "snap": snap, "tgt_share": tshare, "car_share": cshare, "rz": rz}))
        trend, delta = _trend(scores)
        rows.append({
            "player_id": pid, "name": short_name(p), "pos": pos, "team": p.get("team") or "FA",
            "injury": p.get("injury_status") or "",
            "trend": trend, "trend_delta": delta,
            "weeks": wk_rows, "season": season_luck(pid),
        })
    order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
    rows.sort(key=lambda r: (order[r["pos"]], -((r["season"] or {}).get("xpts") or 0)))

    # League-wide: buy-low targets on other teams, and my sell-high candidates.
    buy = []
    for rid, owner, pids in other_teams:
        for pid in pids:
            pos = pos_of(pid)
            s = season_luck(pid) if pos else None
            if not s or s["label"] != "Due for more":
                continue
            if s["xpts"] < {"QB": 15, "RB": 9, "WR": 9, "TE": 7}[pos]:
                continue   # bad luck on a small role isn't worth chasing
            p = players[pid]
            buy.append({"player_id": pid, "roster_id": rid, "owner": owner, "name": short_name(p),
                        "pos": pos, "team": p.get("team") or "FA", **s})
    buy.sort(key=lambda r: r["diff"])
    sell = [{"player_id": r["player_id"], "name": r["name"], "pos": r["pos"], "team": r["team"], **r["season"]}
            for r in rows if r["season"] and r["season"]["label"] == "Running hot"]
    sell.sort(key=lambda r: -r["diff"])

    return {
        "weeks": weeks,
        "players": rows,
        "buy_low": buy[:8],
        "sell_high": sell,
        "ep_through": max(ep_weeks) if ep_weeks else None,
        "has_ep": bool(ep),
    }
