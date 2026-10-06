#!/usr/bin/env python3
"""Entry point. Examples:

  python run.py                      # scheduled run: does whatever is due right now (or nothing)
  python run.py --mode auto          # manual "run now": build the list for the current mode and publish
  python run.py --mode free_agent    # force a mode: waiver_prelim | waiver_final | free_agent | game_day
  python run.py --mode game_day --now 2026-10-11T10:05-04:00 --dry-run   # test as if it were Sunday 10:05 AM ET
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from ffwaiver import notify, render, schedule
from ffwaiver.pipeline import DOCS, ROOT, Skip, build


def load_config():
    with open(os.path.join(ROOT, "config.json")) as f:
        cfg = json.load(f)
    # Environment variables override config.json (handy for GitHub secrets / forks).
    for key, env in (("sleeper_username", "SLEEPER_USERNAME"), ("league_id", "SLEEPER_LEAGUE_ID"),
                     ("season", "SLEEPER_SEASON"), ("my_roster_id", "SLEEPER_ROSTER_ID")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    if os.environ.get("SITE_URL"):
        cfg.setdefault("site", {})["url"] = os.environ["SITE_URL"]
    if os.environ.get("NOTIFICATIONS_ENABLED"):
        cfg.setdefault("notifications", {})["enabled"] = os.environ["NOTIFICATIONS_ENABLED"].lower() in ("1", "true", "yes")
    cfg.setdefault("tuning", {}).setdefault("players_cache_hours", 12)
    cfg["tuning"].setdefault("trending_spike_min_adds", 10000)
    cfg["tuning"].setdefault("list_size", 20)
    cfg.setdefault("waivers", {"day": "Tuesday", "hour_et": 3, "minute_et": 0})
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="scheduled",
                    choices=["scheduled", "auto", "waiver_prelim", "waiver_final", "free_agent", "game_day"])
    ap.add_argument("--now", help="pretend the current time is this ISO timestamp (testing)")
    ap.add_argument("--dry-run", action="store_true", help="print the result, don't write docs/ or notify")
    ap.add_argument("--out", help="write the page to this folder instead of docs/")
    args = ap.parse_args()

    cfg = load_config()
    now = datetime.fromisoformat(args.now).astimezone(timezone.utc) if args.now else datetime.now(timezone.utc)
    manual = args.mode != "scheduled"

    if args.mode == "scheduled":
        job = schedule.due_job(now)
        if not job:
            print(f"Nothing scheduled at {schedule.fmt_et(now)}. Exiting quietly.")
            return 0
    elif args.mode == "auto":
        m = schedule.display_mode(now)
        job = {"waiver": "waiver_final_check", "free_agent": "free_agent", "game_day": "game_day"}[m]
    else:
        job = args.mode
    print(f"{schedule.fmt_et(now)}: job={job} manual={manual}")

    try:
        data, publish, reasons, should_notify = build(cfg, now, job, manual=manual)
    except Skip as s:
        print(f"Skipped: {s}")
        return 0

    lines = [f"{data['badge']['text']} | week {data['week']} | stats through week {data['stats_week']}"]
    if data.get("alert"):
        lines.append("ALERT: " + data["alert"]["text"])
    for n in data.get("notices") or []:
        lines.append("notice: " + n)
    for p in data["picks"]:
        if p.get("rank"):
            tags = " ".join(t["text"] for t in p["tags"])
            lines.append(f"{p['rank']:>2}. {p['name']} ({p['pos']}, {p['team']}) [{p['availability_label']}] {tags}")
            lines.append(f"    {p['reason']}")
            lines.append(f"    Drop: {p['drop']} | {p['advice']}")
    lines.append(f"Change reasons: {reasons or 'none'}")
    summary = "\n".join(lines)
    print("\n" + summary)
    if args.dry_run and os.environ.get("GITHUB_ACTIONS"):
        # Show the list as an annotation on the run page too.
        esc = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::notice title=Preview ({job})::{esc}")

    if args.dry_run:
        if args.out:
            render.write(data, args.out)
            print(f"Page written to {args.out}")
        return 0
    render.write(data, args.out or DOCS)
    print(f"Published to {args.out or DOCS}")
    if should_notify:
        print("Notification:", notify.send(cfg, data, reasons))
    return 0


if __name__ == "__main__":
    sys.exit(main())
