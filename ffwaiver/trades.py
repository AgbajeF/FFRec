"""Trade values, a trade analyzer and a trade suggester.

Values come from free data that DynastyProcess republishes on GitHub every week:
  - redraft / keeper leagues: FantasyPros rest-of-season consensus ranks (db_fpecr_latest.csv),
    turned into trade values with DynastyProcess's own value curve
  - dynasty leagues: DynastyProcess player values (values-players.csv), 1QB or superflex
FantasyCalc (unofficial API, values built from real trades) is blended in when it answers.
FantasyPros ids are mapped to Sleeper ids with db_playerids.csv.

A trade is judged two ways:
  - market value: what each side gives up, with a small premium for the single best player
  - team impact: how much each team's best starting lineup (plus a little bench depth) improves,
    after dropping its weakest players to stay under the roster limit
"""
import csv
import io
import json
import math
import os
import time
from itertools import combinations

from . import sleeper_api
from .http import get_json, get_text
from .recommend import SLOT_ELIG, fantasy_pos, norm_name, short_name

DP = "https://raw.githubusercontent.com/dynastyprocess/data/master/files"
FANTASYCALC = "https://api.fantasycalc.com/values/current"

# DynastyProcess's curve: value = 10500 * e^(-0.0235 * rank). #1 ~ 10,000, #50 ~ 3,200, #100 ~ 1,000.
CURVE_TOP, CURVE_K = 10500, 0.0235
DECAY = 0.85          # 2nd-best player in a package counts 85%, 3rd 72%... (studs cost more than depth)
BENCH_N, BENCH_W = 4, 0.2
FAIR_PCT = 10         # market values within 10% = fair
NO_TRADE_POS = {"K", "DEF"}
FP_POS = {"DST": "DEF"}
FP_TEAMS = {"GBP": "GB", "JAC": "JAX", "KCC": "KC", "LVR": "LV", "NEP": "NE", "NOS": "NO", "SFO": "SF", "TBB": "TB"}


def curve(rank):
    return round(CURVE_TOP * math.exp(-CURVE_K * rank))


def _csv(url):
    return list(csv.DictReader(io.StringIO(get_text(url))))


def fp_to_sleeper(cache_path, max_age_hours=72):
    """{fantasypros_id: sleeper_id}, cached because the source file is ~2.5 MB."""
    try:
        with open(cache_path) as f:
            c = json.load(f)
        if time.time() - c["fetched_at"] < max_age_hours * 3600:
            return c["ids"]
    except (OSError, ValueError, KeyError):
        c = None
    try:
        ids = {r["fantasypros_id"]: r["sleeper_id"] for r in _csv(f"{DP}/db_playerids.csv")
               if r.get("fantasypros_id") not in (None, "", "NA") and r.get("sleeper_id") not in (None, "", "NA")}
    except Exception:
        if c:
            return c["ids"]
        raise
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({"fetched_at": time.time(), "ids": ids}, f)
    return ids


def _match(row_id, name, pos, team, ids, by_name):
    if pos == "DEF":
        return FP_TEAMS.get(team, team) or None
    sid = ids.get(row_id)
    if sid:
        return sid
    return by_name.get((norm_name(name), pos))


def _name_index(players):
    out = {}
    for pid, p in players.items():
        if p.get("position") and p.get("position") != "DEF":
            out.setdefault((norm_name(short_name(p)), p["position"]), pid)
    return out


def ros_values(players, ids):
    """Redraft: FantasyPros rest-of-season overall ranks (+ K/DST position ranks) -> values."""
    rows = _csv(f"{DP}/db_fpecr_latest.csv")
    by_name = _name_index(players)
    vals, scraped = {}, None
    for r in rows:
        if r.get("page_type") != "redraft-overall":
            continue
        pos = FP_POS.get(r.get("pos"), r.get("pos"))
        try:
            ecr = float(r["ecr"])
        except (TypeError, ValueError, KeyError):
            continue
        sid = _match(r.get("id"), r.get("player"), pos, r.get("tm"), ids, by_name)
        if sid and sid not in vals:
            vals[sid] = curve(ecr)
            scraped = scraped or r.get("scrape_date")
    return vals, scraped


def dynasty_values(players, ids, superflex):
    rows = _csv(f"{DP}/values-players.csv")
    by_name = _name_index(players)
    vals, scraped = {}, None
    for r in rows:
        try:
            v = float(r["value_2qb" if superflex else "value_1qb"])
        except (TypeError, ValueError, KeyError):
            continue
        sid = _match(r.get("fp_id"), r.get("player"), r.get("pos"), r.get("team"), ids, by_name)
        if sid:
            vals[sid] = round(v)
            scraped = scraped or r.get("scrape_date")
    return vals, scraped


def fantasycalc_values(dynasty, superflex, teams, ppr):
    """{sleeper_id: value on the same curve} from FantasyCalc's ranks. Unofficial; may fail."""
    data = get_json(FANTASYCALC, {"isDynasty": str(dynasty).lower(), "numQbs": 2 if superflex else 1,
                                  "numTeams": teams, "ppr": ppr}, timeout=30, retries=1)
    out = {}
    for row in data or []:
        sid = str((row.get("player") or {}).get("sleeperId") or "")
        rank = row.get("overallRank")
        if sid and isinstance(rank, (int, float)) and rank > 0:
            out[sid] = curve(rank)
    return out


def scoring_adjust(vals, players, nfl_rows, rec_pts):
    """FantasyPros ranks are full PPR. Re-order them for the league's points per catch using each
    player's season so far (nflverse), then hand the same set of values back out in the new order,
    so the value scale doesn't change. Half PPR moves pass catchers down and runners/QBs up a bit."""
    if rec_pts == 1 or not nfl_rows:
        return vals, 0
    tot = {}
    for r in nfl_rows:
        if r.get("gsis_id"):
            a = tot.setdefault(r["gsis_id"], [0.0, 0.0, 0])
            a[0] += r["fantasy_points"]
            a[1] += r["receptions"]
            a[2] += 1
    ratio = {}
    for sid in vals:
        a = tot.get(((players.get(sid) or {}).get("gsis_id") or "").strip())
        if not a or a[2] < 2:
            continue
        ppr, league_pts = a[0] + a[1], a[0] + rec_pts * a[1]
        if ppr / a[2] >= 3:
            ratio[sid] = max(0.0, league_pts) / ppr
    if len(ratio) < 20:
        return vals, 0
    mid = sorted(ratio.values())[len(ratio) // 2]
    order = sorted(vals, key=lambda sid: -vals[sid] * ratio.get(sid, mid) / mid)
    scale = sorted(vals.values(), reverse=True)
    return dict(zip(order, scale)), len(ratio)


def load_values(league, players, ids_cache, nfl_rows=None, league_format="redraft"):
    """Returns (values {sleeper_id: int}, source label, notices).
    league_format: "redraft", "dynasty", or "auto" (use Sleeper's league type)."""
    notices = []
    settings = league.get("settings") or {}
    dynasty = league_format == "dynasty" or (league_format == "auto" and settings.get("type") == 2)
    rec_pts = (league.get("scoring_settings") or {}).get("rec", 1)
    slots = league.get("roster_positions") or []
    superflex = "SUPER_FLEX" in slots or slots.count("QB") >= 2
    ids = fp_to_sleeper(ids_cache)
    if dynasty:
        vals, scraped = dynasty_values(players, ids, superflex)
        label = "DynastyProcess dynasty values"
    else:
        vals, scraped = ros_values(players, ids)
        label = "FantasyPros rest-of-season ranks"
    if scraped:
        label += f" ({scraped})"
    if not dynasty and rec_pts != 1:
        vals, n = scoring_adjust(vals, players, nfl_rows, rec_pts)
        fmt = {0: "standard", 0.5: "half PPR"}.get(rec_pts, f"{rec_pts:g} PPR")
        if n:
            label += f", adjusted for {fmt}"
        else:
            notices.append(f"Values are full PPR this week (season stats unavailable to adjust for {fmt}).")
    try:
        fc = fantasycalc_values(dynasty, superflex, league.get("total_rosters") or 12, rec_pts)
    except Exception:
        fc = {}
        notices.append("FantasyCalc values unavailable; using FantasyPros only.")
    if fc:
        for sid, v in fc.items():
            vals[sid] = round((vals[sid] + v) / 2) if sid in vals else v
        label += " + FantasyCalc"
    return vals, label, notices


# --------------------------------------------------------------------------- team math

def best_lineup(pids, values, pos_of, slots):
    """Greedy best lineup by value, most restrictive slots first. Returns {pid: slot}."""
    order = sorted(range(len(slots)), key=lambda i: len(SLOT_ELIG[slots[i]]))
    starters = {}
    for i in order:
        elig = SLOT_ELIG[slots[i]]
        pool = [p for p in pids if p not in starters and pos_of.get(p) in elig]
        if pool:
            best = max(pool, key=lambda p: values.get(p, 0))
            starters[best] = slots[i]
    return starters


def team_score(pids, values, pos_of, slots):
    starters = best_lineup(pids, values, pos_of, slots)
    bench = sorted((values.get(p, 0) for p in pids if p not in starters and pos_of.get(p) not in NO_TRADE_POS),
                   reverse=True)[:BENCH_N]
    return sum(values.get(p, 0) for p in starters) + BENCH_W * sum(bench), starters


def after_trade(pids, give, get, values, pos_of, slots):
    """Roster after the trade; extra incoming players force drops of the weakest non-starters."""
    new = [p for p in pids if p not in give] + list(get)
    extra = len(new) - len(pids)
    if extra > 0:
        starters = best_lineup(new, values, pos_of, slots)
        droppable = sorted((p for p in new if p not in starters and p not in get), key=lambda p: values.get(p, 0))
        drop = set(droppable[:extra])
        new = [p for p in new if p not in drop]
    return new


def package_value(pids, values):
    return round(sum(v * DECAY ** i for i, v in enumerate(sorted((values.get(p, 0) for p in pids), reverse=True))))


def verdict(give_value, get_value):
    top = max(give_value, get_value) or 1
    pct = round(100 * (get_value - give_value) / top)
    if abs(pct) <= FAIR_PCT:
        text = "Fair trade"
    elif pct > 0:
        text = "You win this trade"
    else:
        text = "You'd be overpaying"
    return pct, text


def analyze(my_pids, their_pids, give, get, values, pos_of, slots):
    give_value, get_value = package_value(give, values), package_value(get, values)
    pct, text = verdict(give_value, get_value)
    out = {"give_value": give_value, "get_value": get_value, "pct": pct, "verdict": text}
    for side, pids, out_, in_ in (("me", my_pids, give, get), ("them", their_pids, get, give)):
        before, old_st = team_score(pids, values, pos_of, slots)
        new = after_trade(pids, out_, in_, values, pos_of, slots)
        after, new_st = team_score(new, values, pos_of, slots)
        out[side] = {
            "delta": round(after - before), "delta_pct": round(100 * (after - before) / (before or 1), 1),
            "new_starters": [p for p in new_st if p not in old_st],
            "lost_starters": [p for p in old_st if p not in new_st],
            "dropped": [p for p in pids if p not in out_ and p not in new],
        }
    return out


# --------------------------------------------------------------------------- suggester

def _names(pids, players):
    return " + ".join(short_name(players.get(p)) for p in pids) or "nothing"


def _reason(res, give, get, players):
    me, them = res["me"], res["them"]
    parts = []
    mine = [p for p in me["new_starters"] if p in get]
    benched = [p for p in me["lost_starters"] if p not in give]
    if mine:
        parts.append(f"{_names(mine, players)} would start for you"
                     + (f", pushing {_names(benched, players)} to the bench" if benched else "") + ".")
    theirs = [p for p in them["new_starters"] if p in give]
    if theirs and them["delta"] > 0:
        parts.append(f"It helps them too: {_names(theirs, players)} would start for them.")
    elif res["pct"] < 0:
        parts.append("They come out ahead on value, which makes it an easy yes for them.")
    else:
        parts.append("They add depth without weakening their lineup.")
    if me["dropped"]:
        parts.append(f"You'd need to drop {_names(me['dropped'], players)}.")
    return " ".join(parts)


def suggest(my_pids, others, values, pos_of, slots, players, per_team=2, limit=8, pool=12):
    """others: [(roster_id, name, pids)]. Trades that help my lineup, don't hurt theirs, and are fair-ish."""
    def tradeable(pids):
        c = [p for p in pids if pos_of.get(p) not in NO_TRADE_POS and values.get(p, 0) >= 300]
        return sorted(c, key=lambda p: -values.get(p, 0))[:pool]

    my_c = tradeable(my_pids)
    my_base = team_score(my_pids, values, pos_of, slots)[0] or 1
    out = []
    for rid, name, their_pids in others:
        their_c = tradeable(their_pids)
        cands = []
        shapes = [(1, 1), (2, 1), (1, 2)]
        for ng, nr in shapes:
            for give in combinations(my_c, ng):
                gv = package_value(give, values)
                for get in combinations(their_c, nr):
                    rv = package_value(get, values)
                    # They must get at least ~90% of the market value back, and I shouldn't overpay by >25%.
                    if gv < 0.9 * rv or gv > 1.25 * rv:
                        continue
                    res = analyze(my_pids, their_pids, list(give), list(get), values, pos_of, slots)
                    if res["me"]["delta"] <= 0.01 * my_base:
                        continue
                    # They say yes if their lineup improves, or if it barely dips but they win on value.
                    their_base = res["them"]["delta"] / (res["them"]["delta_pct"] / 100) if res["them"]["delta_pct"] else 1
                    if res["them"]["delta"] < 0 and not (gv >= 1.05 * rv and res["them"]["delta"] >= -0.02 * abs(their_base)):
                        continue
                    score = res["me"]["delta"] + 0.5 * res["them"]["delta"] - 0.3 * max(0, gv - rv)
                    cands.append((score, give, get, res))
        cands.sort(key=lambda c: -c[0])
        seen = set()
        for score, give, get, res in cands:
            key = give[0], get[0]
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "roster_id": rid, "team": name, "give": list(give), "get": list(get),
                "give_names": [short_name(players.get(p)) for p in give],
                "get_names": [short_name(players.get(p)) for p in get],
                "verdict": res["verdict"], "pct": res["pct"],
                "give_value": res["give_value"], "get_value": res["get_value"],
                "my_delta_pct": res["me"]["delta_pct"], "their_delta_pct": res["them"]["delta_pct"],
                "reason": _reason(res, give, get, players), "_score": score,
            })
            if len(seen) >= per_team:
                break
    out.sort(key=lambda s: -s["_score"])
    used, final = {}, []
    for s in out:
        # Don't build the whole list around one player.
        if any(used.get(p, 0) >= 2 for p in s["give"] + s["get"]):
            continue
        for p in s["give"] + s["get"]:
            used[p] = used.get(p, 0) + 1
        s.pop("_score")
        final.append(s)
        if len(final) >= limit:
            break
    return final


# --------------------------------------------------------------------------- league trades

def recent_trades(league_id, cur_week, values, players, team_names, weeks_back=4):
    out = []
    for w in range(max(1, cur_week - weeks_back + 1), cur_week + 1):
        try:
            txs = sleeper_api.transactions(league_id, w) or []
        except Exception:
            continue
        for tx in txs:
            if tx.get("type") != "trade" or tx.get("status") != "complete":
                continue
            sides = []
            for rid in tx.get("roster_ids") or []:
                got = [pid for pid, to in (tx.get("adds") or {}).items() if to == rid]
                picks = [f"{d.get('season')} round {d.get('round')} pick" for d in tx.get("draft_picks") or []
                         if d.get("owner_id") == rid]
                sides.append({"team": team_names.get(rid, f"Team {rid}"),
                              "got": [short_name(players.get(p)) for p in got] + picks,
                              "value": package_value(got, values)})
            if len(sides) >= 2:
                lead = max(sides, key=lambda s: s["value"])
                low = min(s["value"] for s in sides)
                close = lead["value"] - low <= FAIR_PCT / 100 * (lead["value"] or 1)
                out.append({"week": w, "created": tx.get("status_updated") or tx.get("created"), "sides": sides,
                            "summary": "Even so far" if close else f"{lead['team']} is ahead by today's values"})
    out.sort(key=lambda t: -(t.get("created") or 0))
    return out[:6]


def build(league_id, league, rosters, users, players, my_roster, cur_week, ids_cache,
          nfl_rows=None, league_format="redraft"):
    """Everything the Trades section of the page needs. Raises if the value source is down."""
    values, source, notices = load_values(league, players, ids_cache, nfl_rows, league_format)
    slots = [s for s in league.get("roster_positions") or [] if s in SLOT_ELIG]
    positions = set().union(*[SLOT_ELIG[s] for s in slots]) if slots else {"QB", "RB", "WR", "TE", "K", "DEF"}
    pos_of = {}
    owner_names = {u.get("user_id"): (u.get("metadata") or {}).get("team_name") or u.get("display_name")
                   for u in users}
    team_names, teams = {}, []
    for r in rosters:
        rid = r.get("roster_id")
        team_names[rid] = owner_names.get(r.get("owner_id")) or f"Team {rid}"
        pids = [p for p in r.get("players") or [] if p in players]
        for p in pids:
            pos_of[p] = fantasy_pos(players[p], positions)
        teams.append((rid, team_names[rid], pids))
    my_rid = my_roster.get("roster_id")
    my_pids = next(p for rid, _, p in teams if rid == my_rid)
    others = [t for t in teams if t[0] != my_rid]

    deadline = (league.get("settings") or {}).get("trade_deadline")
    past_deadline = bool(deadline) and deadline < 99 and cur_week > deadline
    if past_deadline:
        notices.append(f"Your league's trade deadline (week {deadline}) has passed.")
    suggestions = [] if past_deadline else suggest(my_pids, others, values, pos_of, slots, players)
    return {
        "source": source,
        "notices": notices,
        "deadline": deadline if deadline and deadline < 99 else None,
        "slots": slots,
        "slot_elig": {s: sorted(SLOT_ELIG[s]) for s in set(slots)},
        "bench_n": BENCH_N, "bench_w": BENCH_W, "decay": DECAY, "fair_pct": FAIR_PCT,
        "my_roster_id": my_rid,
        "teams": [{"roster_id": rid, "name": name,
                   "players": sorted(({"id": p, "name": short_name(players.get(p)), "pos": pos_of.get(p),
                                       "team": players[p].get("team") or "FA",
                                       "inj": players[p].get("injury_status") or "",
                                       "value": values.get(p, 0)} for p in pids),
                                     key=lambda x: -x["value"])}
                  for rid, name, pids in teams],
        "suggestions": suggestions,
        "recent": recent_trades(league_id, cur_week, values, players, team_names),
    }
