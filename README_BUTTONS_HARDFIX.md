Patch: buttons hardfix

Replace these files:
- main.py
- db.py
- formatting.py
- keyboards.py
- scheduler.py
- match_card.py
- api_football.py

This patch forces the requested match-post UI:

Buttons inside match post:
- Сделать/Изменить прогноз
- Ожидания от матча / Изменить ожидания
- Мысли после матча / Изменить мысли
- Показать мои данные
- Сегодня
- Следующий
- Меню

Removed from match post:
- Узнать счёт
- Очистить
- Поиск команды
- Автопост

Commands:
- /team or /search for team search
- /alerts, /alerts_on, /alerts_off for autopost
- /clear for clearing personal data of the last opened match
- /source to check the running version

Expected /source version:
local-schedule-2026-06-19-v20-buttons-hardfix

If old buttons still appear after redeploy:
- Railway is running an old deploy/container
- or GitHub did not receive the new keyboards.py
