Patch: playoff bracket/list button

Replace these files:
- main.py
- db.py
- formatting.py
- keyboards.py

What changed:
- added button: Плей-офф
- added commands: /playoffs and /playoff
- playoff view shows knockout matches grouped by stage:
  - 1/16 финала
  - 1/8 финала
  - 1/4 финала
  - 1/2 финала
  - Матч за 3-е место
  - Финал
- each playoff match includes a /match_123 link to open the full match card
- if ESPN has not published the knockout pairs yet, the bot says that playoff matches are not available yet
- the match list buttons under the playoff table also open individual match cards

Important:
- playoff matches come from the PostgreSQL cache after /sync pulls them from ESPN
- press /sync first, then Плей-офф
- if ESPN has placeholders or future pairings, the bot will show them as ESPN provides them

Expected /source version:
external-espn-schedule-v28-playoffs-button
