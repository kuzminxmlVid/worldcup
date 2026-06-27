Patch: external ESPN schedule source

Replace/add these files:
- main.py
- db.py
- scheduler.py
- espn_schedule.py

What changed:
- match schedule is no longer loaded from the local schedule.json file
- /sync now fetches matches from ESPN public scoreboard endpoint
- startup sync also fetches from ESPN
- the bot fetches the whole tournament window from 2026-06-11 to 2026-07-19
- knockout/playoff matches appear as soon as ESPN publishes them or updates teams
- the local PostgreSQL database remains as cache/storage, but it is no longer the source of truth
- existing fixture_id values are preserved when the same match is found, so user predictions/expectations are not lost for already-known matches

Source:
- https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard

Optional Railway variables:
- WORLD_CUP_START_DATE=2026-06-11
- WORLD_CUP_END_DATE=2026-07-19

Commands:
- /sync — refresh schedule from ESPN
- /sync_scores — refresh scores for already played matches
- /source — check source and bot version

Expected /source version:
external-espn-schedule-v26

Important:
ESPN scoreboard is public but unofficial. If ESPN changes JSON format, parser may need an update.
