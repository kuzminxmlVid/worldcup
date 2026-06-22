Hotfix: self-contained team picker

Причина падения:
main.py импортировал team_select_keyboard из keyboards.py.
На Railway фактически лежит keyboards.py без этой функции, поэтому контейнер падает ещё на старте.

Что изменено:
- main.py больше не импортирует team_select_keyboard из keyboards.py
- функция выбора команды теперь находится прямо в main.py как local_team_select_keyboard
- даже если на сервере случайно останется старый keyboards.py, бот больше не упадёт на этом импорте

Replace these files:
- main.py
- keyboards.py

Главное:
Если нужно срочно поднять бота, достаточно заменить main.py.
Но лучше заменить оба файла.

Expected /source version:
local-schedule-2026-06-19-v25-team-picker-selfcontained
