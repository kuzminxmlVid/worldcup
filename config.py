\
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    app_tz: ZoneInfo
    daily_hour: int
    daily_minute: int


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return Config(
        bot_token=bot_token,
        database_url=database_url,
        app_tz=ZoneInfo(os.getenv("APP_TZ", "Europe/Moscow")),
        daily_hour=int(os.getenv("DAILY_HOUR", "10")),
        daily_minute=int(os.getenv("DAILY_MINUTE", "0")),
    )
