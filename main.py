\
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

import db
from api_football import ApiFootballClient
from config import load_config
from formatting import day_bounds_utc, format_matches
from scheduler import setup_scheduler, sync_fixtures


logging.basicConfig(level=logging.INFO)

config = load_config()

bot = Bot(token=config.bot_token)
dp = Dispatcher()

pool = None
api_client = ApiFootballClient(
    api_key=config.api_football_key,
    host=config.api_football_host,
)


@dp.message(Command("start"))
async def start(message: Message):
    await db.add_chat(pool, message.chat.id)
    await message.answer(
        "Готово. Я буду присылать расписание матчей ЧМ.\n\n"
        "Команды:\n"
        "/today — матчи сегодня\n"
        "/tomorrow — матчи завтра\n"
        "/week — матчи на 7 дней\n"
        "/sync — обновить расписание\n"
        "/stop — отписаться"
    )


@dp.message(Command("stop"))
async def stop(message: Message):
    await db.stop_chat(pool, message.chat.id)
    await message.answer("Ок, больше не буду присылать расписание в этот чат.")


@dp.message(Command("sync"))
async def sync(message: Message):
    await message.answer("Обновляю расписание...")
    try:
        count = await sync_fixtures(pool, api_client)
        await message.answer(f"Готово. Обновлено матчей: {count}.")
    except Exception as e:
        logging.exception("Sync failed")
        await message.answer(f"Не получилось обновить расписание: {e}")


@dp.message(Command("today"))
async def today(message: Message):
    day = datetime.now(config.app_tz).date()
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await message.answer(format_matches("🏆 Матчи ЧМ сегодня", rows, config.app_tz))


@dp.message(Command("tomorrow"))
async def tomorrow(message: Message):
    day = datetime.now(config.app_tz).date() + timedelta(days=1)
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await message.answer(format_matches("🏆 Матчи ЧМ завтра", rows, config.app_tz))


@dp.message(Command("week"))
async def week(message: Message):
    today_local = datetime.now(config.app_tz).date()
    start_utc, _ = day_bounds_utc(today_local, config.app_tz)
    _, end_utc = day_bounds_utc(today_local + timedelta(days=7), config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await message.answer(format_matches("🏆 Матчи ЧМ на 7 дней", rows, config.app_tz))


async def main():
    global pool

    pool = await db.create_pool(config.database_url)
    await db.init_db(pool)

    try:
        count = await sync_fixtures(pool, api_client)
        logging.info("Initial sync complete. Matches: %s", count)
    except Exception:
        logging.exception("Initial sync failed")

    scheduler = setup_scheduler(bot, pool, api_client, config)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
