Patch: API-Football score button

Replace/add these files:
- main.py
- db.py
- keyboards.py
- match_card.py
- api_football.py

What changed:
- added button: Узнать счёт
- when pressed, the bot requests score from API-Football
- the bot stores API fixture id in PostgreSQL when it finds the match
- home_goals, away_goals, status_short and status_long are saved to the existing matches table
- the match card image is updated with the score
- if the old card image message can be edited, it is edited
- if Telegram refuses to edit it, the bot sends a new updated card
- a table match_card_messages stores the last card message id per chat/user/match

Railway variables:
- API_FOOTBALL_KEY=your_key

Optional variables:
- API_FOOTBALL_LEAGUE_ID=1
- API_FOOTBALL_SEASON=2026

Test:
1. Add API_FOOTBALL_KEY to Railway
2. Redeploy
3. /start
4. Open any match card
5. Press Узнать счёт

Notes:
- Free API-Football plan is limited, so do not spam the score button.
- If API-Football has not published World Cup 2026 fixtures yet, the bot will say it could not find the match.
