Patch: remove more buttons + lock predictions at kickoff

Replace these files:
- main.py
- keyboards.py

Match post buttons now:
- Сделать прогноз / Изменить прогноз before kickoff
- Прогноз закрыт after kickoff
- Ожидания от матча / Изменить ожидания
- Мысли после матча / Изменить мысли
- Сегодня
- Следующий

Removed from match post:
- Показать мои данные
- Меню

Menu is still available through /menu.
Team search is still available through /team or /search.
Autopost is still available through /alerts.
Clear personal data for last opened match is still available through /clear.

Prediction lock:
- if current UTC time is greater than or equal to kickoff_utc, the prediction button becomes “Прогноз закрыт”
- direct attempts to save a prediction after kickoff are also blocked
- Telegram inline buttons cannot be truly disabled, so the locked button only explains that prediction is closed

Expected /source version:
local-schedule-2026-06-19-v21-prediction-lock-buttons
