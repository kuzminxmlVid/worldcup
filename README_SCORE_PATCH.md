Patch: ESPN score button

Replace/add these files:
- main.py
- db.py
- keyboards.py
- match_card.py
- api_football.py

What changed:
- removed dependency on API-Football paid season access
- api_football.py now uses ESPN public scoreboard JSON endpoint
- no API key is required for score lookup
- button remains the same: Узнать счёт
- the bot stores ESPN event id in the existing api_fixture_id field
- home_goals, away_goals, status_short and status_long are saved to PostgreSQL
- the match card image is updated with the score
- if the old card can be edited, it is edited
- if Telegram refuses to edit it, the bot sends a new updated card

Railway:
- API_FOOTBALL_KEY is no longer needed for this feature
- you can leave it in Railway, it will be ignored

Test:
1. Redeploy
2. Open any match card
3. Press Узнать счёт

Notes:
- ESPN endpoint is public but unofficial/undocumented.
- If ESPN changes the endpoint or team names, the bot may fail to find a match.
