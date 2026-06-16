\
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    api_football_key: str
    api_football_host: str
    app_tz: ZoneInfo
    daily_hour: int
    daily_minute: int


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN")
    database_url = os.getenv("DATABASE_URL")
    api_key = os.getenv("API_FOOTBALL_KEY")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if not api_key:
        raise RuntimeError("API_FOOTBALL_KEY is not set")

    return Config(
        bot_token=bot_token,
        database_url=database_url,
        api_football_key=api_key,
        api_football_host=os.getenv("API_FOOTBALL_HOST", "v3.football.api-sports.io"),
        app_tz=ZoneInfo(os.getenv("APP_TZ", "Europe/Moscow")),
        daily_hour=int(os.getenv("DAILY_HOUR", "10")),
        daily_minute=int(os.getenv("DAILY_MINUTE", "0")),
    )
