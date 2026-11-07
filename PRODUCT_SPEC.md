# Waiver Wire: product spec and change log

This document says in plain language what the site does and why, and records every change to it.
The technical setup is in [README.md](README.md). Update this file in the same pull request as any
change to how the site behaves.

**Live site:** https://agbajef.github.io/FFRec/
**League:** Sleeper, half-PPR redraft, FAAB waivers that run Tuesday at 3 AM Eastern.

---

## What the site is for

It's one phone-friendly page that answers four questions each week:

1. **Who should I pick up?** (Waivers tab)
2. **Who should I start?** (Start/Sit tab)
3. **Whose role is growing, and who's been lucky or unlucky?** (Trends tab)
4. **What trades would help me?** (Trades tab)

It rebuilds itself on a schedule, needs no login or server, and is free to run.

## When it updates

| When (Eastern) | What you see |
|---|---|
| Sunday 11:45 PM | Preliminary waiver list (yellow) |
| Monday night through 2 AM Tuesday | Final waiver list (green), published once all games are final and stats are in |
| Tuesday to Saturday, every 2 hours from 8 AM to midnight | Free-agent list (blue). It only republishes when something important changes. |
| Sunday 10:00 AM and 11:45 AM | Game-day check (orange): inactives, late injuries, backups who just got the job |

"Something important" means one of these:
- One of your players gets worse (for example, Questionable to Out).
- A starter's injury opens a role for an available player.
- A player's adds spike across Sleeper.
- Someone new enters the top 5.
- The best lineup now differs from the one you have set in Sleeper.
- One of your starters is forecast very windy or snowy weather.

Discord or email alerts can be turned on for these moments. They're off right now.

## Waivers tab

A ranked list of available players, built for your roster rather than a generic top 20.

- **How players are scored:** recent usage (snaps, target share, carries, red-zone looks) counts more
  than recent points. Next week's projection, the opponent, Sleeper trending adds and any opened
  role (the starter ahead of him is out) also count.
- **Fit to your team:** positions where you're thin, injured or on bye move up. So do players who'd
  beat your weakest starter.
- **For each player:** whether he's a free agent or on waivers, a suggested FAAB bid range, and who
  to drop.

## Start/Sit tab

Added November 7, 2026. This tab ranks your own roster for next week's lineup.

- **Change in Sleeper:** who to start and who to bench compared with the lineup you have set now.
  It also warns you about empty starting slots. A player whose game has already kicked off is never
  moved.
- **Best lineup and bench:** each player's Sleeper projection, nudged up or down for the game's Vegas
  line and the weather. Each row shows the over/under, the spread, the team's implied total (how many
  points Vegas expects them to score) and its rank that week, plus the mid-game forecast. A bench
  player within about a point of a starter is marked **Close call**.
- **Games by over/under:** every game, highest total first, with both teams' implied totals and which
  of your players are in it.

How the nudge works, kept small on purpose because Sleeper's projection already accounts for some of this:
- A team expected to score 10% more than the average team that week gets about +5%, capped at ±15%.
- Defenses are judged by how many points their opponent is expected to score.
- Running backs on big favorites get a small bump. Receivers and tight ends on big underdogs get +3%,
  since trailing teams throw more.
- Wind of 15 mph or more, rain and snow hurt kickers most, then QBs, receivers and tight ends. Dome
  games are marked and skip the forecast.

## Trends tab

Added November 7, 2026. It shows how your players are actually being used, and whether their points
match that usage.

- **Your players:** a week-by-week table for the last 6 weeks, newest first. It shows fantasy points,
  expected points, share of offensive snaps, targets and share of team targets, air yards (how far
  downfield he's targeted), carries, and red-zone chances. Which columns you see depends on position.
  A **Role growing** or **Role shrinking** tag appears when his last two weeks of usage differ clearly
  from the weeks before.
- **Expected points ("xPts"):** what an average player would have scored with the same targets and
  carries from the same spots on the field. When actual points run well below expected, it's usually
  bad touchdown luck that tends to even out. When they run well above, it usually cools off.
  - **Due for more:** scoring at least 2.5 points a game below expected (3.5 for QBs, 2 for TEs) over
    3 or more games. Hold him, or buy low.
  - **Running hot:** the same gap, but above expected. A sell-high candidate.
  - **On track:** in between.
- **Sell high:** your own players who are running hot.
- **Buy low around your league:** players on other teams who have a real role and are due for more.
  Each one shows who owns him and has a **Try a trade** button that opens the trade analyzer with him
  already selected.

## Trades tab

Added October 28, 2026.

- **Suggested trades:** 1-for-1, 2-for-1 and 1-for-2 deals that improve your starting lineup, don't
  hurt the other team's, and are within about 10% on value.
- **Trade analyzer:** pick a team and players on each side to get a verdict (fair, you win, or you
  overpay), how each lineup changes, and who you'd have to drop.
- **Recent league trades,** graded with today's values.

Player values come from FantasyPros rest-of-season ranks, re-ordered for half PPR and blended with
FantasyCalc where it's available.

## Where the data comes from

Every source is free and needs no account or API key.

| Source | Used for |
|---|---|
| Sleeper (official API) | Your league, rosters, lineup, transactions, players, trending adds |
| Sleeper (unofficial) | Weekly stats and projections |
| ESPN (unofficial) | Game status, injuries, news, betting lines (DraftKings) |
| nflverse | Season stats, target share, air yards, schedule, backup betting lines, roof type |
| ffverse ffopportunity | Expected fantasy points per player per week (the model behind nflverse's opportunity data) |
| Open-Meteo | Game-time weather forecast for outdoor stadiums |
| FantasyPros (via DynastyProcess) | Trade values |
| FantasyCalc | Trade values, when available |

If any source is down, the page still builds and shows a short note about what's missing.

## Ideas not built yet

These came out of the November 7 brainstorm, in the suggested order:

1. **Matchup heat map:** points each defense allows by position over the last 4 weeks, plus your
   players' next 3 opponents. (nflverse)
2. **Playoff odds:** simulate the rest of the season to show your chances and which games matter most.
   (Sleeper)
3. **Weekly matchup preview:** your projected lineup against your opponent's, with win probability.
   (Sleeper)
4. **Playoff-week schedule strength:** how easy each player's weeks 14 to 17 look. (nflverse)

---

## Change log

Newest first.

### November 7, 2026: Trends tab
- New **Trends** tab with week-by-week usage for your players (snaps, targets, target share, air
  yards, carries, red-zone chances) and tags for roles that are growing or shrinking.
- Expected points versus actual points, which labels each player Due for more, Running hot or On track.
- **Sell high** list for your roster, and a **Buy low around your league** list with a one-tap link
  into the trade analyzer.

### November 7, 2026: Start/Sit tab
- New **Start/Sit** tab with Vegas over/unders, spreads, implied team totals and game-time weather.
- It tells you exactly which players to swap in Sleeper, and flags close calls.
- The page now also republishes when the best lineup changes or a starter gets very windy or snowy
  weather.
- Test runs now print the suggested lineup in the GitHub Actions log.

### October 28, 2026: Trades tab
- New **Trades** tab with suggested trades, a trade analyzer and grades for recent league trades.

### October 20, 2026: Launch
- Waiver and free-agent list built for your roster, with FAAB bids and drop suggestions.
- Automatic schedule: Sunday preliminary list, Monday final list, free-agent checks during the week
  and game-day checks on Sunday.
- Optional Discord and email alerts.
