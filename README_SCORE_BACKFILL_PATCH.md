Patch: open score API backfill

Replace/add these files:
- main.py
- db.py
- scheduler.py
- api_football.py

What changed:
- score provider is ESPN public scoreboard JSON endpoint
- no API key is required
- added bulk score backfill for all already played matches
- on every deploy/startup, bot tries to update scores for already played matches
- scheduler runs the same backfill every 30 minutes
- added command /sync_scores to manually update scores for all already played matches
- scores are stored in matches.home_goals, matches.away_goals, matches.status_short, matches.status_long
- existing personal match posts show score as Telegram spoiler when re-opened or refreshed by user action

Important:
- ESPN endpoint is public but unofficial/undocumented.
- If ESPN changes JSON structure or team names, parser may need update.
- Existing already-sent Telegram personal posts are not automatically edited, because the bot does not store their message ids. New/opened match posts will show the hidden score after DB update.

Expected /source version:
local-schedule-2026-06-19-v22-open-score-backfill

Useful commands:
- /sync_scores — update scores for all already played matches
- /source — check bot version
