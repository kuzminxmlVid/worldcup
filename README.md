# World Cup Telegram Bot

Телеграм-бот для расписания матчей Чемпионата мира по футболу.

Источник данных: API-Football / API-Sports.

## Что умеет

- `/start` — подписать чат на ежедневное расписание.
- `/stop` — отписать чат.
- `/today` — матчи сегодня.
- `/tomorrow` — матчи завтра.
- `/week` — матчи на 7 дней.
- `/sync` — вручную обновить расписание из API.
- Автоматически присылает расписание каждый день утром.
- Напоминает о матче за 1 час.
- Хранит данные в PostgreSQL.

## Переменные окружения

Смотри `.env.example`.

На Railway нужно добавить:

```env
BOT_TOKEN=
DATABASE_URL=
API_FOOTBALL_KEY=
API_FOOTBALL_HOST=v3.football.api-sports.io
APP_TZ=Europe/Moscow
DAILY_HOUR=10
DAILY_MINUTE=0
```

## Railway

1. Создай репозиторий на GitHub.
2. Залей туда эти файлы.
3. В Railway создай New Project.
4. Подключи GitHub repo.
5. Добавь PostgreSQL.
6. В сервисе бота добавь переменные окружения.
7. `DATABASE_URL` возьми из Postgres-плагина Railway.
8. Deploy.

Railway запустит процесс из `Procfile`:

```bash
worker: python main.py
```

## API-Football

Для ЧМ-2026 используются:

```txt
GET /fixtures?league=1&season=2026
GET /standings?league=1&season=2026
```

`league=1`, `season=2026`.
