"""Scoring and recommendation logic.

Input: a `ctx` dict assembled by pipeline.py. Output: the page data dict.
Every signal is optional; missing data lowers its weight instead of failing.
"""
import math
import re
from datetime import datetime, timedelta, timezone

from . import schedule
from .points import def_stats, fantasy_points, played

SLOT_ELIG = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"}, "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "REC_FLEX": {"WR", "TE"}, "WRRB_FLEX": {"WR", "RB"},
    "DL": {"DL"}, "LB": {"LB"}, "DB": {"DB"}, "IDP_FLEX": {"DL", "LB", "DB"},
}
POS_SCALE = {"QB": 24, "RB": 18, "WR": 18, "TE": 13, "K": 11, "DEF": 11, "DL": 10, "LB": 12, "DB": 10}
POS_NAMES = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "kicker", "DEF": "defense"}
OUT_STATUSES = {"Out", "IR", "Sus", "PUP", "NA", "DNR"}
BAD_STATUSES = OUT_STATUSES | {"Doubtful"}
STATUS_WORDS = {"Out": "Out", "IR": "on IR", "Sus": "suspended", "PUP": "on PUP", "Doubtful": "Doubtful",
                "Questionable": "Questionable", "NA": "not active", "DNR": "out"}
SEVERITY = {None: 0, "": 0, "Questionable": 1, "Doubtful": 2, "Out": 3, "PUP": 3, "Sus": 3, "IR": 4, "NA": 3, "DNR": 3}

WEIGHTS = {
    # usage is deliberately weighted above raw points
    "waiver":     {"usage": .30, "points": .10, "proj": .20, "opp": .20, "trend": .10, "matchup": .10},
    "free_agent": {"usage": .20, "points": .10, "proj": .25, "opp": .25, "trend": .10, "matchup": .10},
    "game_day":   {"usage": .15, "points": .10, "proj": .30, "opp": .30, "trend": .05, "matchup": .10},
}


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def norm_name(s):
    s = (s or "").lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def player_name(p):
    if not p:
        return "Unknown"
    if p.get("position") == "DEF":
        return f"{p.get('first_name') or p.get('team')} {p.get('last_name') or 'D/ST'}".strip()
    return p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get("player_id")


def short_name(p):
    if p and p.get("position") == "DEF":
        return f"{p.get('team')} D/ST"
    return player_name(p)


def fantasy_pos(p, league_positions):
    pos = p.get("position")
    if pos in league_positions:
        return pos
    for fp in p.get("fantasy_positions") or []:
        if fp in league_positions:
            return fp
    return None


def ago_words(dt, now):
    secs = (now - dt).total_seconds()
    if secs < 3600:
        return "in the last hour"
    if secs < 86400:
        return "today" if schedule.to_et(dt).date() == schedule.to_et(now).date() else "last night"
    return schedule.to_et(dt).strftime("%A")


# --------------------------------------------------------------------------- engine

class Engine:
    def __init__(self, ctx):
        self.ctx = ctx
        self.now = ctx["now"]
        self.mode = ctx["mode"]
        self.players = ctx["players"]
        self.scoring = ctx["league"].get("scoring_settings") or {}
        self.slots = [s for s in ctx["league"].get("roster_positions") or [] if s in SLOT_ELIG]
        self.league_positions = set().union(*[SLOT_ELIG[s] for s in self.slots]) if self.slots else {"QB", "RB", "WR", "TE", "K", "DEF"}
        self.weekly = ctx["weekly"]           # {week: {pid: stats}}
        self.weeks = sorted(self.weekly)[-3:]
        self.proj = ctx.get("projections") or {}
        self.notices = list(ctx.get("notices") or [])
        self._apply_espn_injuries()
        self._team_totals()
        self._games()
        self._nflverse()
        self._trending()
        self._news()
        self._depth()

    # ---- preparation -----------------------------------------------------
    def _apply_espn_injuries(self):
        """Upgrade a Sleeper injury status when ESPN has a newer, worse one (e.g. ruled Out)."""
        self.espn_inj = {}
        by_key = {}
        for pid, p in self.players.items():
            if p.get("team"):
                by_key[(norm_name(player_name(p)), p["team"])] = pid
        for inj in self.ctx.get("espn_injuries") or []:
            pid = by_key.get((norm_name(inj.get("name")), inj.get("team")))
            if not pid:
                continue
            self.espn_inj[pid] = inj
            p = self.players[pid]
            espn_status = {"Injured Reserve": "IR", "Suspension": "Sus"}.get(inj.get("status"), inj.get("status"))
            if SEVERITY.get(espn_status, 0) > SEVERITY.get(p.get("injury_status"), 0):
                p["injury_status"] = espn_status
                if inj.get("date"):
                    p["news_updated"] = max(p.get("news_updated") or 0, int(inj["date"].timestamp() * 1000))

    def _team_totals(self):
        self.team_tgt, self.team_car = {}, {}
        for w in self.weeks:
            tt, tc = {}, {}
            for pid, st in self.weekly[w].items():
                team = (self.players.get(pid) or {}).get("team")
                if not team or (self.players.get(pid) or {}).get("position") == "DEF":
                    continue
                tt[team] = tt.get(team, 0) + (st.get("rec_tgt") or 0)
                tc[team] = tc.get(team, 0) + (st.get("rush_att") or 0)
            self.team_tgt[w], self.team_car[w] = tt, tc

    def _games(self):
        self.opp_next, self.kick_next = {}, {}
        for g in self.ctx.get("games_next") or []:
            if g.get("home") and g.get("away"):
                self.opp_next[g["home"]] = (g["away"], "vs")
                self.opp_next[g["away"]] = (g["home"], "@")
                self.kick_next[g["home"]] = self.kick_next[g["away"]] = g.get("kickoff")
        self.have_schedule = bool(self.opp_next)
        self.played_this = set()
        for g in self.ctx.get("games_this") or []:
            if g.get("kickoff") and g["kickoff"] <= self.now:
                self.played_this.update([g.get("home"), g.get("away")])
        ppg = self.ctx.get("team_ppg") or {}
        self.team_ppg = ppg

    def _nflverse(self):
        self.nfl_ts = {}
        rows = self.ctx.get("nfl_rows") or []
        for r in rows:
            if r["week"] in self.weeks and r["gsis_id"]:
                self.nfl_ts[(r["gsis_id"], r["week"])] = r
        self.season_avg = {}
        tot = {}
        for r in rows:
            if r["gsis_id"]:
                a = tot.setdefault(r["gsis_id"], [0.0, 0])
                a[0] += r["fantasy_points"] + (self.scoring.get("rec") or 0) * r["receptions"]
                a[1] += 1
        self.season_avg = {k: v[0] / v[1] for k, v in tot.items() if v[1]}
        self.pa = self.ctx.get("pa_by_pos") or {}
        self.pa_rank = {}
        for pos in ("QB", "RB", "WR", "TE"):
            vals = sorted([(v, k[0]) for k, v in self.pa.items() if k[1] == pos])
            n = len(vals)
            for i, (_, team) in enumerate(vals):
                self.pa_rank[(team, pos)] = 100 * i / max(1, n - 1)   # 100 = gives up the most
        ppg = sorted([(v, t) for t, v in self.team_ppg.items()])
        n = len(ppg)
        self.ppg_rank = {t: 100 * i / max(1, n - 1) for i, (_, t) in enumerate(ppg)}  # 100 = best offense

    def _trending(self):
        self.trend = {}
        lst = self.ctx.get("trending") or []
        for i, t in enumerate(lst):
            pid = str(t.get("player_id"))
            self.trend[pid] = {"count": int(t.get("count") or 0), "rank": i + 1}
        self.trend_max = max([t["count"] for t in self.trend.values()] or [1])

    def _news(self):
        self.news_by_espn = {}
        for a in self.ctx.get("espn_news") or []:
            for aid in a["athlete_ids"]:
                cur = self.news_by_espn.get(aid)
                if a.get("published") and (not cur or a["published"] > cur["published"]):
                    self.news_by_espn[aid] = a

    def _depth(self):
        self.depth = {}
        for pid, p in self.players.items():
            dcp, order, team = p.get("depth_chart_position"), p.get("depth_chart_order"), p.get("team")
            if team and dcp and isinstance(order, int):
                self.depth.setdefault((team, dcp), []).append((order, pid))
        for v in self.depth.values():
            v.sort()

    # ---- per-player features ---------------------------------------------
    def stats_for(self, pid, week):
        p = self.players.get(pid) or {}
        wk = self.weekly.get(week) or {}
        return def_stats(wk, pid) if p.get("position") == "DEF" else wk.get(pid)

    def opportunity(self, pid):
        """(strength 0-100, blocker_pid) if a starter ahead on the depth chart is out."""
        p = self.players[pid]
        dcp, order, team = p.get("depth_chart_position"), p.get("depth_chart_order"), p.get("team")
        if not (team and dcp and isinstance(order, int)) or order <= 1:
            return 0, None
        ahead = [(o, q) for o, q in self.depth.get((team, dcp), []) if o < order]
        if not ahead or len(ahead) > 2:
            return 0, None
        out = [q for _, q in ahead if self.players[q].get("injury_status") in BAD_STATUSES]
        if len(out) != len(ahead):   # someone healthy is still ahead of him
            return 0, None
        blocker = ahead[0][1]
        st = self.players[blocker].get("injury_status")
        strength = 100 if st in OUT_STATUSES else 65
        if p.get("position") == "WR":
            strength *= 0.8
        return strength, blocker

    def features(self, pid):
        p = self.players[pid]
        pos = fantasy_pos(p, self.league_positions)
        team = p.get("team")
        gsis = (p.get("gsis_id") or "").strip()
        weeks = []
        for w in self.weeks:
            st = self.stats_for(pid, w) or {}
            if not played(st) and pos != "DEF":
                weeks.append({"week": w, "played": False, "pts": 0})
                continue
            snp = (st.get("off_snp") or 0) / st["tm_off_snp"] if st.get("tm_off_snp") else None
            tgt_share = (st.get("rec_tgt") or 0) / self.team_tgt[w].get(team, 0) if self.team_tgt[w].get(team) else None
            nv = self.nfl_ts.get((gsis, w))
            if nv and nv["target_share"]:
                tgt_share = nv["target_share"]
            car_share = (st.get("rush_att") or 0) / self.team_car[w].get(team, 0) if self.team_car[w].get(team) else None
            weeks.append({
                "week": w, "played": bool(st), "pts": fantasy_points(st, self.scoring),
                "snap": snp, "tgt_share": tgt_share, "car_share": car_share,
                "targets": st.get("rec_tgt") or (nv or {}).get("targets") or 0,
                "carries": st.get("rush_att") or (nv or {}).get("carries") or 0,
                "rz": (st.get("rec_rz_tgt") or 0) + (st.get("rush_rz_att") or 0),
            })
        played_w = [w for w in weeks if w["played"]]
        recent_avg = sum(w["pts"] for w in played_w) / len(played_w) if played_w else 0.0
        last_pts = weeks[-1]["pts"] if weeks else 0.0

        usage_by_week = [self._usage_score(pos, w) for w in weeks]
        valid = [(u, i) for i, u in enumerate(usage_by_week) if u is not None]
        if valid:
            wts = [0.2, 0.3, 0.5][-len(usage_by_week):]
            num = sum(u * wts[i] for u, i in valid)
            den = sum(wts[i] for _, i in valid)
            usage = num / den
            latest = usage_by_week[-1]
            prior = [u for u in usage_by_week[:-1] if u is not None]
            trend = (latest - sum(prior) / len(prior)) if (latest is not None and prior) else 0.0
            usage_c = clamp(0.75 * usage + 0.25 * clamp(50 + 2 * trend))
        else:
            usage, trend, usage_c = None, 0.0, 50.0 if pos in ("K", "DEF") else 0.0

        proj_stats = def_stats(self.proj, pid) if pos == "DEF" else self.proj.get(pid)
        proj = fantasy_points(proj_stats, self.scoring) if proj_stats else None

        opp_team, ha = self.opp_next.get(team, (None, None))
        bye = self.have_schedule and team not in self.opp_next
        if bye:
            matchup = 0.0
        elif pos in ("QB", "RB", "WR", "TE") and (opp_team, pos) in self.pa_rank:
            matchup = self.pa_rank[(opp_team, pos)]
        elif pos == "DEF" and opp_team in self.ppg_rank:
            matchup = 100 - self.ppg_rank[opp_team]
        elif pos == "K" and team in self.ppg_rank:
            matchup = self.ppg_rank[team]
        else:
            matchup = 50.0

        opp_strength, blocker = self.opportunity(pid)
        tr = self.trend.get(pid)
        trend_c = 100 * math.log10(1 + tr["count"]) / math.log10(1 + self.trend_max) if tr else 0.0

        news_time, news_text = None, None
        if p.get("news_updated"):
            news_time = datetime.fromtimestamp(p["news_updated"] / 1000, tz=timezone.utc)
        art = self.news_by_espn.get(str(p.get("espn_id") or ""))
        last = (p.get("last_name") or "").lower()
        if (art and art.get("published") and last and last in art["headline"].lower()
                and (not news_time or art["published"] >= news_time - timedelta(hours=6))):
            news_time, news_text = art["published"], art["headline"]

        kickoff = self.kick_next.get(team)
        locked = bool(kickoff and kickoff <= self.now) if self.mode != "waiver" else False
        scale = POS_SCALE.get(pos, 15)
        return {
            "pid": pid, "pos": pos, "team": team, "weeks": weeks,
            "recent_avg": recent_avg, "last_pts": last_pts,
            "usage": usage, "usage_trend": trend, "usage_c": usage_c,
            "points_c": clamp((0.6 * recent_avg + 0.4 * last_pts) / scale * 100),
            "proj": proj, "proj_c": clamp(proj / scale * 100) if proj is not None else None,
            "opp_team": opp_team, "home_away": ha, "bye": bye, "matchup_c": matchup,
            "opp_c": opp_strength, "blocker": blocker,
            "trend_c": trend_c, "trend_count": tr["count"] if tr else 0, "trend_rank": tr["rank"] if tr else None,
            "news_time": news_time, "news_text": news_text,
            "injury": p.get("injury_status"), "kickoff": kickoff, "locked": locked,
            "season_avg": self.season_avg.get(gsis),
        }

    def _usage_score(self, pos, w):
        if not w.get("played") or pos in ("K", "DEF") or w.get("snap") is None:
            return None
        snap = clamp(w["snap"] * 100)
        tgt = (w["tgt_share"] or 0) * 100
        car = (w["car_share"] or 0) * 100
        rz = w["rz"]
        if pos == "RB":
            return clamp(0.35 * snap + 0.35 * clamp(car / 60 * 100) + 0.2 * clamp(tgt / 15 * 100) + 0.1 * clamp(rz / 4 * 100))
        if pos == "WR":
            return clamp(0.35 * snap + 0.45 * clamp(tgt / 25 * 100) + 0.2 * clamp(rz / 3 * 100))
        if pos == "TE":
            return clamp(0.35 * snap + 0.45 * clamp(tgt / 20 * 100) + 0.2 * clamp(rz / 3 * 100))
        if pos == "QB":
            return clamp(0.8 * snap + 0.2 * clamp(car / 15 * 100))
        return snap

    def composite(self, f):
        wts = dict(WEIGHTS[self.mode])
        if f["proj_c"] is None:  # projections unavailable: lean on usage and recent points
            extra = wts.pop("proj")
            wts["usage"] += extra * 0.6
            wts["points"] += extra * 0.4
        vals = {"usage": f["usage_c"], "points": f["points_c"], "proj": f["proj_c"],
                "opp": f["opp_c"], "trend": f["trend_c"], "matchup": f["matchup_c"]}
        contrib = {k: wts[k] * (vals[k] or 0) for k in wts}
        score = sum(contrib.values())
        # A player whose own role is blocked shouldn't win on trending alone.
        if f["opp_c"] == 0 and f["usage_c"] < 25 and f["points_c"] < 25 and (f["proj_c"] or 0) < 30:
            score *= 0.75
        return score, contrib

    # ---- my roster ---------------------------------------------------------
    def week_value(self, f):
        """Expected points next week (0 if on bye or out)."""
        if f["bye"] or (f["injury"] in OUT_STATUSES):
            return 0.0
        v = f["proj"] if f["proj"] is not None else f["recent_avg"]
        if f["injury"] == "Doubtful":
            v *= 0.25
        elif f["injury"] == "Questionable":
            v *= 0.85
        return v

    def best_lineup(self, feats, healthy_only=True):
        """Greedy lineup: most restrictive slots first. Returns [(slot, pid or None, value)]."""
        order = sorted(range(len(self.slots)), key=lambda i: len(SLOT_ELIG[self.slots[i]]))
        used, lineup = set(), [None] * len(self.slots)
        for i in order:
            slot = self.slots[i]
            best = None
            for pid, f in feats.items():
                if pid in used or f["pos"] not in SLOT_ELIG[slot]:
                    continue
                v = self.week_value(f) if healthy_only else max(f["proj"] or 0, f["recent_avg"], f["season_avg"] or 0)
                if healthy_only and v <= 0:
                    continue
                if best is None or v > best[1]:
                    best = (pid, v)
            if best:
                used.add(best[0])
                lineup[i] = (slot, best[0], best[1])
            else:
                lineup[i] = (slot, None, 0.0)
        return lineup

    def keep_value(self, f, comp):
        """How much I'd hate to drop this player (protects injured studs)."""
        p = self.players[f["pid"]]
        rank = p.get("search_rank") or 9999
        pedigree = clamp(100 - rank / 3) if rank < 300 else 0
        season = clamp((f["season_avg"] or 0) / POS_SCALE.get(f["pos"], 15) * 100)
        return max(comp, 0.8 * pedigree, season)

    # ---- main ------------------------------------------------------------
    def run(self):
        ctx = self.ctx
        rostered = ctx["rostered"]
        me = ctx["my_roster"]
        reserve = set(me.get("reserve") or []) | set(me.get("taxi") or [])
        my_ids = [pid for pid in (me.get("players") or []) if pid in self.players]

        my_feats = {}
        for pid in my_ids:
            if fantasy_pos(self.players[pid], self.league_positions):
                my_feats[pid] = self.features(pid)
        lineup = self.best_lineup({k: v for k, v in my_feats.items() if k not in reserve})
        ideal = self.best_lineup({k: v for k, v in my_feats.items() if k not in reserve}, healthy_only=False)
        starters = {pid for _, pid, _ in lineup if pid}
        my_keep = {}
        for pid, f in my_feats.items():
            comp, _ = self.composite(f)
            my_keep[pid] = self.keep_value(f, comp)

        # My roster problems: players who'd start if healthy but are now out.
        sleeper_starters = set(me.get("starters") or [])
        ideal_starters = {pid for _, pid, _ in ideal if pid}
        my_out = []
        for pid in (ideal_starters | sleeper_starters):
            f = my_feats.get(pid)
            if f and f["injury"] in OUT_STATUSES and pid not in reserve and not f["locked"]:
                my_out.append(pid)
        my_out.sort(key=lambda x: -my_keep.get(x, 0))
        out_positions = {my_feats[pid]["pos"]: pid for pid in reversed(my_out)}

        # Candidates
        cands = []
        for pid, p in self.players.items():
            if pid in rostered or not p.get("team"):
                continue
            pos = fantasy_pos(p, self.league_positions)
            if not pos:
                continue
            if p.get("position") != "DEF" and p.get("active") is False:
                continue
            has_signal = (any(self.stats_for(pid, w) for w in self.weeks) or pid in self.proj
                          or pid in self.trend or (p.get("search_rank") or 9999) < 400)
            if not has_signal:
                continue
            cands.append(self.features(pid))

        weakest = {}
        for pos in self.league_positions:
            vals = [v for slot, pid, v in lineup if pos in SLOT_ELIG[slot]]
            weakest[pos] = min(vals) if vals else 0.0
        depth_count = {}
        for pid, f in my_feats.items():
            if pid not in reserve and self.week_value(f) > 0:
                depth_count[f["pos"]] = depth_count.get(f["pos"], 0) + 1

        results = []
        for f in cands:
            comp, contrib = self.composite(f)
            pos = f["pos"]
            wv = self.week_value(f)
            upgrade = wv - weakest.get(pos, 0.0)
            scale = POS_SCALE.get(pos, 15)
            dedicated = sum(1 for s in self.slots if SLOT_ELIG[s] == {pos})
            flex = 0.5 if any(pos in SLOT_ELIG[s] and len(SLOT_ELIG[s]) > 1 for s in self.slots) else 0
            thin = dedicated + flex + (1 if pos in ("RB", "WR") else 0) - depth_count.get(pos, 0)
            mult = 1 + 0.10 * clamp(thin, 0, 3)
            if thin <= -2:
                mult *= 0.9
            if upgrade > 0:
                mult += min(0.3, upgrade / scale * 0.6)
            elif pos in ("K", "DEF"):
                mult *= 0.5
            elif pos == "QB" and dedicated == 1 and "SUPER_FLEX" not in self.slots:
                mult *= 0.7
            replaces = out_positions.get(pos)
            if replaces and self.mode != "waiver":
                mult += 0.25
            elif replaces:
                mult += 0.15
            streamer = pos in ("QB", "TE", "K", "DEF") and upgrade >= 1.0 and not f["bye"]
            if streamer and self.mode != "waiver":
                mult += 0.1

            # Player's own health / availability
            inj = f["injury"]
            if inj in ("IR", "PUP", "Sus", "NA", "DNR"):
                mult *= 0.3
            elif inj == "Out":
                mult *= 0.45 if self.mode == "waiver" else 0.25
            elif inj == "Doubtful":
                mult *= 0.6
            elif inj == "Questionable":
                mult *= 0.92
            if f["bye"]:
                mult *= 0.85 if self.mode == "waiver" else 0.4
            if f["locked"]:
                mult *= 0.55
            if pos in ("K", "DEF"):   # streamers matter, but rarely more than a real skill-position add
                mult *= 0.5 if self.mode == "waiver" else 0.65

            score = comp * mult
            # A clear path to starting (the starter ahead is out) is the strongest waiver signal there is.
            if (f["opp_c"] >= 100 and pos in ("RB", "QB", "TE") and inj not in BAD_STATUSES
                    and (pos != "QB" or upgrade > 0)):
                score += 12 * min(mult, 1.0)
            results.append({"f": f, "score": score, "comp": comp, "contrib": contrib,
                            "upgrade": upgrade, "streamer": streamer, "replaces": replaces})

        results.sort(key=lambda r: -r["score"])
        size = ctx.get("list_size", 20)

        # Keep a few per position beyond the overall top list so the filter tabs aren't empty.
        top = results[:size]
        per_pos = {}
        for r in results:
            per_pos.setdefault(r["f"]["pos"], []).append(r)
        extras = []
        for pos, lst in per_pos.items():
            have = sum(1 for r in top if r["f"]["pos"] == pos)
            extras += [r for r in lst[: max(0, 5 - have)] if r not in top]
        shown = top + sorted(extras, key=lambda r: -r["score"])

        prev_rank = {p["player_id"]: p["rank"] for p in (ctx.get("prev") or {}).get("picks", []) if p.get("rank")}
        faab = self._faab_info()
        picks = []
        for i, r in enumerate(shown):
            rank = i + 1 if i < size else None
            picks.append(self._card(r, rank, prev_rank, my_feats, my_keep, starters, reserve, faab))

        alert = self._alert(my_out, my_feats, results)
        return {
            "picks": picks,
            "alert": alert,
            "notices": self.notices,
            "my_roster_status": {pid: (self.players[pid].get("injury_status") or "") for pid in my_ids},
            "faab": faab,
            "my_lineup": [{"slot": s, "player": short_name(self.players.get(pid)) if pid else None,
                           "proj": round(v, 1)} for s, pid, v in lineup],
        }

    # ---- presentation helpers ---------------------------------------------
    def _faab_info(self):
        league = self.ctx["league"]
        st = league.get("settings") or {}
        me = self.ctx["my_roster"].get("settings") or {}
        wtype = st.get("waiver_type")
        if wtype == 2:
            budget = st.get("waiver_budget") or 0
            used = me.get("waiver_budget_used") or 0
            return {"type": "faab", "budget": budget, "remaining": max(0, budget - used)}
        return {"type": "priority", "position": me.get("waiver_position"),
                "teams": st.get("num_teams") or league.get("total_rosters")}

    def _availability(self, f):
        """('fa'|'waivers', label, claim_by_iso)."""
        ctx = self.ctx
        pid = f["pid"]
        deadline = ctx["waiver_deadline"]
        dropped = ctx.get("recent_drops", {}).get(pid)
        clear_days = (ctx["league"].get("settings") or {}).get("waiver_clear_days") or 0
        if self.mode == "waiver" and (f["team"] in self.played_this or dropped):
            return "waivers", f"On waivers: claim by {schedule.fmt_et(deadline)}", deadline.isoformat()
        if dropped and clear_days:
            clears = dropped + timedelta(days=clear_days)
            if clears > self.now:
                clears_et = schedule.to_et(clears)
                run = clears_et.replace(hour=ctx["waiver_hour"], minute=0, second=0, microsecond=0)
                if run < clears_et:
                    run += timedelta(days=1)
                return "waivers", f"On waivers: claim by {schedule.fmt_et(run)}", run.isoformat()
        if f["locked"]:
            return "waivers", f"Game started: on waivers until {schedule.fmt_et(deadline)}", deadline.isoformat()
        return "fa", "Free agent: add now", None

    def _advice(self, r, kind, faab):
        pos = r["f"]["pos"]
        s = r["score"]
        if kind == "fa":
            return "No bid needed. Add him directly."
        if faab["type"] == "faab":
            rem = faab["remaining"]
            if pos in ("K", "DEF"):
                lo, hi = 0, 2
            elif s >= 75:
                lo, hi = 18, 30
            elif s >= 60:
                lo, hi = 10, 18
            elif s >= 48:
                lo, hi = 4, 10
            elif s >= 38:
                lo, hi = 1, 4
            else:
                lo, hi = 0, 1
            dlo, dhi = math.floor(rem * lo / 100), max(math.ceil(rem * hi / 100), 1 if hi else 0)
            if hi <= 2:
                return f"Bid ${dlo}–${dhi} (minimal; {lo}–{hi}% of your ${rem})"
            return f"Bid ${dlo}–${dhi} ({lo}–{hi}% of your ${rem} left)"
        if s >= 60:
            return "Worth using a high waiver priority."
        return "Don't burn a high priority; claim only if it costs a low one."

    def _drop(self, r, my_feats, my_keep, starters, reserve):
        f = r["f"]
        pos = f["pos"]
        mine = {pid: g for pid, g in my_feats.items() if pid not in reserve}
        if pos in ("K", "DEF"):
            same = [pid for pid, g in mine.items() if g["pos"] == pos]
            if same:
                worst = min(same, key=lambda x: (self.week_value(mine[x]), my_keep[x]))
                return worst, False
        counts = {}
        for g in mine.values():
            counts[g["pos"]] = counts.get(g["pos"], 0) + 1
        options = []
        for pid, g in mine.items():
            if pid in starters and self.week_value(g) > 0:
                continue
            if g["pos"] in ("K", "DEF") and counts.get(g["pos"], 0) <= 1:
                continue
            kv = my_keep[pid] * (0.5 if g["pos"] in ("K", "DEF") else 1)  # extra K/DEF is cheap
            options.append((kv, pid))
        if not options:
            return None, False
        kv, pid = min(options)
        return pid, kv >= r["comp"]

    def _reason(self, r, my_feats):
        f = r["f"]
        p = self.players[f["pid"]]
        pos = f["pos"]
        opp = f"{f['home_away']} {f['opp_team']}" if f["opp_team"] else None
        # 1. replacing one of my out starters (free agent / game day)
        if r["replaces"] and self.mode != "waiver" and (f["opp_c"] or r["upgrade"] > 0):
            mine = self.players[r["replaces"]]
            first = short_name(p).split(" ")[-1]
            why = (f"{first} is his direct backup on the depth chart" if f["blocker"] == r["replaces"]
                   else f"he also takes over for {short_name(self.players[f['blocker']])}" if f["blocker"]
                   else f"projects {f['proj']:.1f} pts{(' ' + opp) if opp else ''}" if f["proj"] is not None
                   else f"averages {f['recent_avg']:.1f} pts")
            return f"Covers your {STATUS_WORDS.get(mine.get('injury_status'), 'out')} {POS_NAMES.get(pos, pos)} {short_name(mine)}; {why}.", True
        # 2. depth-chart opening from an injury / suspension
        if f["opp_c"] >= 60 and f["blocker"]:
            b = self.players[f["blocker"]]
            st = STATUS_WORDS.get(b.get("injury_status"), b.get("injury_status") or "out")
            when = ""
            news_t = b.get("news_updated")
            if news_t:
                dt = datetime.fromtimestamp(news_t / 1000, tz=timezone.utc)
                if (self.now - dt) < timedelta(days=4):
                    when = f" {ago_words(dt, self.now)}"
            body = f" ({b.get('injury_body_part')})" if b.get("injury_body_part") and st not in ("suspended",) else ""
            verb = "was ruled" if st in ("Out", "Doubtful") else "is"
            return f"Starter {short_name(b)} {verb} {st}{body}{when}; {short_name(p).split(' ')[-1]} is next on the depth chart.", True
        # 3. trending spike
        if f["trend_rank"] and f["trend_rank"] <= 15 and f["trend_count"] >= self.ctx.get("spike_min", 10000):
            extra = f" ({f['news_text']})" if f["news_text"] else ""
            return f"Trending: likely news{extra}. Added in {f['trend_count']:,} Sleeper leagues in the last day.", True
        # 4. usage jump
        ws = [w for w in f["weeks"] if w.get("played")]
        if len(ws) >= 2 and pos in ("RB", "WR", "TE") and f["usage_trend"] >= 8:
            last, prev = ws[-1], ws[:-1]
            prev_snap = [w["snap"] for w in prev if w.get("snap") is not None]
            if last.get("snap") is not None and prev_snap:
                ps = sum(prev_snap) / len(prev_snap)
                touches = f"{last['targets']:.0f} targets" if pos != "RB" else f"{last['carries']:.0f} carries and {last['targets']:.0f} targets"
                return f"Role is growing: {last['snap']*100:.0f}% of snaps last week (up from {ps*100:.0f}%) with {touches}.", False
        # 5. streamer
        if r["streamer"] and f["proj"] is not None:
            return f"Streaming option: projects {f['proj']:.1f} pts{(' ' + opp) if opp else ''}, {r['upgrade']:.1f} more than your current {POS_NAMES.get(pos, pos)}.", False
        # 6. steady usage
        if f["usage"] is not None and f["usage"] >= 55 and ws:
            last = ws[-1]
            share = (f"{last['tgt_share']*100:.0f}% target share" if pos in ("WR", "TE") and last.get("tgt_share")
                     else f"{last['carries']:.0f} carries" if pos == "RB" else "a full-time role")
            snap = f"{last['snap']*100:.0f}% of snaps" if last.get("snap") is not None else "steady snaps"
            return f"Locked-in role: {snap} and {share} last week, averaging {f['recent_avg']:.1f} pts in your scoring.", False
        if f["proj"] is not None and f["proj"] >= 5:
            return f"Projects {f['proj']:.1f} pts next week{(' ' + opp) if opp else ''} in your scoring.", False
        if f["recent_avg"] > 0:
            return f"Averaging {f['recent_avg']:.1f} pts over his last {len(ws)} games in your scoring.", False
        return "Best remaining option at the position for depth.", False

    def _card(self, r, rank, prev_rank, my_feats, my_keep, starters, reserve, faab):
        f = r["f"]
        p = self.players[f["pid"]]
        kind, label, claim_iso = self._availability(f)
        reason, news_driven = self._reason(r, my_feats)
        drop_pid, close = self._drop(r, my_feats, my_keep, starters, reserve)
        drop = None
        if drop_pid:
            dp = self.players[drop_pid]
            drop = f"{short_name(dp)} ({my_feats[drop_pid]['pos']})" + (" — close call" if close else "")
        tags = []
        if prev_rank and rank:
            old = prev_rank.get(f["pid"])
            if old is None:
                tags.append({"kind": "new", "text": "NEW"})
            elif old > rank:
                tags.append({"kind": "up", "text": "▲ moved up"})
            elif old < rank:
                tags.append({"kind": "down", "text": "▼ moved down"})
        news_iso = None
        if news_driven:
            t = f["news_time"]
            if f["blocker"] and self.players[f["blocker"]].get("news_updated"):
                t = datetime.fromtimestamp(self.players[f["blocker"]]["news_updated"] / 1000, tz=timezone.utc)
            if t and self.now - t < timedelta(days=3):
                news_iso = t.isoformat()
        stats = {
            "weeks": [{"week": w["week"], "pts": round(w["pts"], 1),
                       "snap": round(w["snap"] * 100) if w.get("snap") is not None else None,
                       "targets": round(w.get("targets") or 0), "carries": round(w.get("carries") or 0),
                       "rz": round(w.get("rz") or 0)} for w in f["weeks"] if w.get("played")],
            "proj": round(f["proj"], 1) if f["proj"] is not None else None,
            "avg": round(f["recent_avg"], 1),
            "adds_24h": f["trend_count"],
            "opponent": f"{f['home_away']} {f['opp_team']}" if f["opp_team"] else ("BYE" if f["bye"] else None),
            "score": round(r["score"], 1),
        }
        return {
            "rank": rank,
            "player_id": f["pid"],
            "name": player_name(p),
            "pos": f["pos"],
            "team": f["team"],
            "injury": f["injury"] or None,
            "availability": kind,
            "availability_label": label,
            "claim_by": claim_iso,
            "reason": reason,
            "drop": drop,
            "advice": self._advice(r, kind, faab),
            "tags": tags,
            "news_iso": news_iso,
            "trending_spike": bool(f["trend_rank"] and f["trend_rank"] <= 15 and f["trend_count"] >= self.ctx.get("spike_min", 10000)),
            "opportunity": bool(f["blocker"] and f["opp_c"] >= 60),
            "replaces": r["replaces"],
            "stats": stats,
        }

    def _alert(self, my_out, my_feats, results):
        if not my_out:
            return None
        parts, repl = [], []
        for pid in my_out[:2]:
            p = self.players[pid]
            pos = my_feats[pid]["pos"]
            st = (p.get("injury_status") or "OUT").upper()
            st = {"IR": "ON IR", "SUS": "SUSPENDED", "NA": "OUT", "PUP": "ON PUP"}.get(st, st)
            parts.append(f"Your {pos} {short_name(p)} is {st}.")
            best = next((r for r in results if r["f"]["pos"] == pos and not r["f"]["locked"]
                         and r["f"]["injury"] not in BAD_STATUSES and not r["f"]["bye"]), None)
            if best:
                repl.append(player_name(self.players[best["f"]["pid"]]))
        text = " ".join(parts)
        if repl:
            text += " Best replacement" + ("s" if len(repl) > 1 else "") + ": " + ", ".join(repl) + "."
        return {"text": text, "player_ids": my_out}


def recommend(ctx):
    return Engine(ctx).run()
