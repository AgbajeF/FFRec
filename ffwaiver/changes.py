"""Decide whether a new list is different enough from the last published one to
republish and notify. Small reshuffles are ignored on purpose (no spam)."""
from .recommend import SEVERITY

WORSE_ALERT = {"Doubtful", "Out", "IR", "Sus", "PUP"}


def material_changes(new, prev):
    """Return a list of short, human-readable reasons. Empty list = nothing material."""
    if not prev or not prev.get("picks"):
        return ["First list published."]
    reasons = []

    # 1. A player on my roster got worse (e.g. Questionable -> Out)
    old_status = prev.get("my_roster_status") or {}
    names = {p["player_id"]: p["name"] for p in new.get("my_roster", [])}
    for pid, st in (new.get("my_roster_status") or {}).items():
        before = old_status.get(pid, "")
        if st in WORSE_ALERT and SEVERITY.get(st, 0) > SEVERITY.get(before or None, 0):
            reasons.append(f"Your {names.get(pid, 'player')} is now {st}.")

    top = [p for p in new["picks"] if p.get("rank") and p["rank"] <= 20]
    prev_top = [p for p in prev["picks"] if p.get("rank") and p["rank"] <= 20]
    prev_opp = {p["player_id"] for p in prev_top if p.get("opportunity")}
    prev_spike = {p["player_id"] for p in prev_top if p.get("trending_spike")}

    # 2. A starter injury opened up a role for an available player
    for p in top:
        if p.get("opportunity") and p["player_id"] not in prev_opp:
            reasons.append(f"Role opened up: {p['name']} ({p['pos']}, {p['team']}).")

    # 3. Big jump in trending adds
    for p in top:
        if p.get("trending_spike") and p["player_id"] not in prev_spike:
            reasons.append(f"Trending spike: {p['name']} is being added everywhere.")

    # 4. Top-5 change: someone new, or someone moved 2+ spots
    prev_rank = {p["player_id"]: p["rank"] for p in prev_top}
    for p in top[:5]:
        old = prev_rank.get(p["player_id"])
        if old is None or old > 5:
            reasons.append(f"{p['name']} entered the top 5 (#{p['rank']}).")
        elif abs(old - p["rank"]) >= 2:
            reasons.append(f"{p['name']} moved from #{old} to #{p['rank']}.")

    # 5. Start/Sit: the suggested lineup swaps changed, or bad weather hit one of my starters
    ss, pss = new.get("start_sit") or {}, prev.get("start_sit") or {}
    if ss.get("start") and (ss.get("start"), ss.get("sit")) != (pss.get("start"), pss.get("sit")):
        sit = f", bench {', '.join(ss['sit'])}" if ss.get("sit") else ""
        reasons.append(f"Your lineup: start {', '.join(ss['start'])}{sit}.")
    bad = ("Very windy", "Snow")
    prev_bad = {(r.get("player_id"), f["text"].split(" (")[0]) for r in pss.get("lineup") or []
                for f in r.get("flags") or [] if f["text"].startswith(bad)}
    for r in ss.get("lineup") or []:
        for f in r.get("flags") or []:
            key = (r.get("player_id"), f["text"].split(" (")[0])
            if f["text"].startswith(bad) and key not in prev_bad and not r.get("locked"):
                reasons.append(f"Your {r['name']}: {f['text'].lower()} forecast for {r['opp']}.")

    # de-duplicate, keep order
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
