# World Cup Telegram Bot — local schedule version

Эта версия не ходит во внешние API.

Расписание лежит физически в репозитории:

```text
schedule.json
```

Бот при запуске читает этот файл, кладёт 104 матча в PostgreSQL и дальше работает из базы.

## Команды

- `/start`
- `/sync` — перечитать `schedule.json` и перезаписать матчи в Postgres.
- `/source` — проверить, какой локальный файл читает бот и сколько матчей нашёл.
- `/debug` — проверить базу и ближайшие матчи.
- `/today`
- `/tomorrow`
- `/week`
- `/stop`

## Railway переменные

Нужны только:

```env
BOT_TOKEN=
DATABASE_URL=
APP_TZ=Europe/Moscow
DAILY_HOUR=10
DAILY_MINUTE=0
MISE_PYTHON_GITHUB_ATTESTATIONS=false
```

Больше не нужны:

```env
API_FOOTBALL_KEY
API_FOOTBALL_HOST
SCHEDULE_SOURCE_URL
SOURCE_TZ
```

## Проверка после деплоя

В Telegram:

```text
/source
/sync
/debug
/week
```

Нормально:

```text
/source -> Матчей в файле: 104
/sync -> Готово. Загружено матчей: 104.
/debug -> Матчей в базе: 104
```

## Важно

Если в Railway снова будет ошибка `API_FOOTBALL_KEY is not set`, значит Railway запускает старый `config.py`.

В новой версии в коде вообще нет слова `API_FOOTBALL_KEY`.
