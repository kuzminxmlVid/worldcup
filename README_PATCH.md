Patch: reminders fix + team search

Replace these files:
- main.py
- db.py
- keyboards.py
- formatting.py
- scheduler.py

What changed:
- fixed one-hour reminders so one Telegram send error does not kill the whole scheduler job
- reminders now check a 50-70 minute window before kickoff to avoid missing matches during deploy/restart delays
- added logs for reminder checks and successful/failed sends
- added button: Поиск команды
- added commands: /team and /search
- search supports team names in English and common Russian names, for example Португалия, Бразилия, Конго, США
- search returns all matches for the team: played and future

After deploy:
1. Press /start
2. Press Поиск команды
3. Type Португалия or Portugal
4. Check Railway logs for lines like:
   Checking hour reminders...
   Hour reminder sent...
