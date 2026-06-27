Hotfix: ESPN int type parser

Ошибка:
'int' object has no attribute 'get'

Причина:
В ответе ESPN поле event.season.type иногда приходит числом, а не словарём.
Парсер ожидал dict и падал на season_type.get(...).

Что исправлено:
- espn_schedule.py теперь безопасно обрабатывает dict/list поля ESPN
- season.type может быть int/string/dict без падения
- notes, group, venue, competitors тоже обработаны безопаснее
- /sync должен снова работать

Replace these files:
- espn_schedule.py
- main.py

Expected /source version:
external-espn-schedule-v27-int-type-hotfix

After deploy:
1. /source
2. /sync
