Patch: next playoff round list

Replace these files:
- main.py
- db.py
- formatting.py
- keyboards.py

What changed:
- the old Плей-офф button is replaced with Следующий раунд
- the bot no longer sends a huge playoff image/table
- the bot shows only the current next playoff round:
  - first 1/16 финала
  - then 1/8 финала
  - then 1/4 финала
  - then 1/2 финала
  - then Финал
- the next round is chosen automatically from DB:
  - the first playoff stage that still has unfinished matches
- each match includes a /match_123 link in text
- each match also has a separate inline button that opens the match card
- /round and /next_round added
- /playoffs and /playoff still work as aliases, but now show only the next round

Before using:
- press /sync to refresh schedule from ESPN
- then press Следующий раунд or /round

Expected /source version:
external-espn-schedule-v30-next-round-list
