# Waiver Wire

A phone-friendly page that always shows the best waiver and free-agent pickups for **your** Sleeper team.
It rebuilds itself on a schedule with GitHub Actions and is hosted for free on GitHub Pages.
There's no server, database or login.

| When (Eastern) | What the page shows |
|---|---|
| Sun 11:45 PM | **WAIVER CLAIMS: Preliminary list** (yellow) |
| Mon 11:30 PM → Tue 2 AM | Checks every 30 min. Once every game is final and the stats are posted, it publishes the **WAIVER CLAIMS: Final list** (green). If the data still isn't complete at 2 AM, it publishes anyway with a note. |
| Tue → Sat, 8 AM → midnight, every 2 hours | **FREE AGENTS: Add anytime** (blue): news, injuries and practice reports. Thursday's 6 PM check lands before Thursday Night Football. |
| Sun 10:00 AM and 11:45 AM | **GAME DAY: Check before kickoff** (orange): inactives, backups who just got the job, your players ruled Out. |

The free-agent and game-day checks only republish (and notify) when something **material** changes:
one of your players gets worse (e.g. Questionable → Out), a starter's injury opens a role, a player's
adds spike on Sleeper, or someone new enters the top 5. Otherwise they quietly do nothing. The Sunday
preliminary and Monday final lists always publish.

---

## Setup (about 10 minutes, no coding)

1. **Make the repository public.** Free GitHub accounts can only host Pages from public repos.
   On GitHub: *Settings → General → Danger Zone → Change visibility → Public*.
   (Nothing private is stored here. Your league data is already visible to anyone with the league ID.)
2. **Check `config.json`.** It already has your Sleeper username and league ID. Change them here if you
   ever switch leagues. `season` and `my_roster_id` can stay `"auto"`.
3. **Allow the workflow to save the page.** *Settings → Actions → General → Workflow permissions →*
   choose **Read and write permissions** → Save.
4. **Turn on GitHub Pages.** *Settings → Pages → Build and deployment → Source: Deploy from a branch →*
   Branch **main**, folder **/docs** → Save. Your site will be at
   `https://<your-github-name>.github.io/<repo-name>/` (e.g. `https://agbajef.github.io/FFRec/`).
5. **Run it once now.** *Actions → Update waiver wire → Run workflow → Run workflow*. After a minute
   the page appears at the address above. Add it to your phone's home screen.

That's it. The schedule takes over from there.

### Optional: notifications

Off by default. To get a Discord message when a list publishes or urgent news hits your roster:

1. In Discord: *Server Settings → Integrations → Webhooks → New Webhook → Copy Webhook URL*.
2. On GitHub: *Settings → Secrets and variables → Actions → New repository secret*,
   name `DISCORD_WEBHOOK_URL`, paste the URL.
3. In `config.json` set `"notifications": { "enabled": true, ... }`.

To turn notifications off again, set `"enabled": false` (or delete the secret).
Email works the same way: set `notifications.email.enabled` to `true`, fill in `to`,
and add `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` secrets (for Gmail use an app password).

### Run it by hand

*Actions → Update waiver wire → Run workflow*:
- **mode**: `auto` builds the right list for right now. You can also force `waiver_prelim`,
  `waiver_final`, `free_agent` or `game_day`.
- **dry_run**: prints the list in the run log and attaches a preview of the page, without publishing.
- **now**: pretend it's a different time, e.g. `2026-10-11T11:50-04:00` (testing only).

On your own computer (Python 3.10+, no packages needed):

```bash
python run.py --mode auto --dry-run          # print the current list
python -m unittest discover tests            # run the tests
```

---

## How the recommendations work

1. **Available players** = every QB/RB/WR/TE/K/DEF (plus any other position your league starts) not on a roster in your league.
2. **Free agent vs. on waivers.** After games start, players lock onto waivers until Tuesday 3 AM ET.
   Recently dropped players stay on waivers for the league's `waiver_clear_days`.
3. **Points use your league's scoring** (`scoring_settings` from Sleeper). Your league is 0.5 PPR with bonuses.
4. Each player gets a score from:
   - **Usage trend** over the last 3 weeks: snap %, target share, carry share, red-zone looks (weighted more than points)
   - Recent fantasy points
   - Next week's projection
   - **Opportunity**: the starter ahead of him on the depth chart is Out, Doubtful, on IR or suspended
   - Sleeper trending adds (a secondary signal; big spikes get tagged "Trending: likely news")
   - Next week's opponent (points allowed to that position) or bye
5. **Your roster**: positions where you're thin, injured or have byes get a boost, and so do players who'd
   beat your weakest starter. In free-agent and game-day mode, replacements for your Out players and
   QB/TE/K/DEF streamers move up.
6. **FAAB**: a bid range as a % of your remaining budget. (Priority leagues get "worth a high priority?" advice.)
7. **Drop suggestion**: your least valuable bench player, protecting injured stars. K/DEF pickups swap with your current K/DEF.

### Data sources

- **Sleeper official API**: league, rosters, users, transactions, players, trending, NFL state.
  The large player list is cached and refreshed at most every 12 hours (and before each game-day check).
- **Unofficial endpoints** (`ffwaiver/unofficial_sources.py`): Sleeper weekly stats and projections, and
  ESPN's scoreboard, injuries and news. These aren't officially supported and could change. If one fails,
  the page still builds and shows a small note such as "Projections unavailable this week."
- **nflverse** (`ffwaiver/nflverse.py`): season-long weekly stats (target share, opponent points allowed)
  and the schedule. nflverse often posts a week's data on Tuesday; a missing update never breaks a run.

### Files

```
config.json                 your league settings
run.py                      entry point (scheduled or manual)
ffwaiver/schedule.py        Eastern-time schedule, modes, daylight saving handling
ffwaiver/pipeline.py        fetches data, decides preliminary/final, decides whether to publish
ffwaiver/recommend.py       scoring, roster needs, reasons, drops, FAAB advice
ffwaiver/changes.py         "is this a material change?" rules
ffwaiver/render.py          the page (docs/index.html) and docs/data.json
ffwaiver/notify.py          optional Discord / email
.github/workflows/update.yml  schedules + "Run workflow" button
docs/                       the published site; docs/data.json is also the "previous list" used to spot changes
```

### Daylight saving time

GitHub's cron runs in UTC, so each Eastern-time slot is scheduled at both of its possible UTC times.
The script checks the real Eastern time and the run that doesn't match simply exits, so the schedule
is right in both EDT and EST without any changes.

### Troubleshooting

- **The page didn't update.** Open *Actions* and look at the latest run. "Nothing scheduled" or
  "no material changes" are normal. A red run usually means Sleeper itself was down; the next run retries.
- **Schedules stopped.** GitHub pauses scheduled workflows in repos with no activity for 60 days. Each
  published list is a commit, so this only happens in the offseason. Re-enable it from the *Actions* tab.
- **Wrong team.** Set `my_roster_id` in `config.json` to your roster number.
