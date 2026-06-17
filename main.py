import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

import db
from config import load_config
from formatting import day_bounds_utc, format_matches, format_debug, split_telegram_text
from keyboards import main_keyboard
from local_schedule import load_matches, SCHEDULE_PATH
from scheduler import setup_scheduler, sync_fixtures


VERSION = "local-schedule-2026-06-17-v2-pretty"

logging.basicConfig(level=logging.INFO)

config = load_config()

bot = Bot(token=config.bot_token)
dp = Dispatcher()
pool = None


async def send_text(message: Message, text: str):
    for part in split_telegram_text(text):
        await message.answer(part)


async def send_today_text(message: Message):
    day = datetime.now(config.app_tz).date()
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_text(message, format_matches("🏆 Матчи ЧМ сегодня", rows, config.app_tz))


async def send_tomorrow_text(message: Message):
    day = datetime.now(config.app_tz).date() + timedelta(days=1)
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_text(message, format_matches("🏆 Матчи ЧМ завтра", rows, config.app_tz))


async def send_week_text(message: Message):
    today_local = datetime.now(config.app_tz).date()
    start_utc, _ = day_bounds_utc(today_local, config.app_tz)
    _, end_utc = day_bounds_utc(today_local + timedelta(days=7), config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_text(message, format_matches("🏆 Матчи ЧМ на 7 дней", rows, config.app_tz))


@dp.message(Command("start"))
async def start(message: Message):
    await db.add_chat(pool, message.chat.id)
    await message.answer(
        "Готово. Я буду присылать расписание матчей ЧМ.\n\n"
        "Теперь можно пользоваться кнопками снизу или командами.\n\n"
        "Команды:\n"
        "/today — матчи сегодня\n"
        "/tomorrow — матчи завтра\n"
        "/week — матчи на 7 дней\n"
        "/sync — обновить расписание из локального schedule.json\n"
        "/debug — проверить базу\n"
        "/source — проверить локальный файл\n"
        "/stop — отписаться",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("stop"))
async def stop(message: Message):
    await db.stop_chat(pool, message.chat.id)
    await message.answer("Ок, больше не буду присылать расписание в этот чат.")


@dp.message(Command("sync"))
async def sync(message: Message):
    await message.answer("Обновляю расписание из локального файла...")
    try:
        count = await sync_fixtures(pool)
        await message.answer(f"Готово. Загружено матчей: {count}.", reply_markup=main_keyboard())
    except Exception as e:
        logging.exception("Sync failed")
        await message.answer(f"Не получилось обновить расписание: {e}", reply_markup=main_keyboard())


@dp.message(Command("today"))
async def today(message: Message):
    await send_today_text(message)


@dp.message(Command("tomorrow"))
async def tomorrow(message: Message):
    await send_tomorrow_text(message)


@dp.message(Command("week"))
async def week(message: Message):
    await send_week_text(message)


@dp.message(Command("debug"))
async def debug(message: Message):
    count, first_row, last_row, next_rows = await db.get_debug_stats(pool)
    await message.answer(format_debug(count, first_row, last_row, next_rows, config.app_tz), reply_markup=main_keyboard())


@dp.message(Command("source"))
async def source(message: Message):
    try:
        matches = load_matches()
        await message.answer(
            f"Источник: локальный файл\n"
            f"Файл: {SCHEDULE_PATH.name}\n"
            f"Версия кода: {VERSION}\n"
            f"Матчей в файле: {len(matches)}",
            reply_markup=main_keyboard(),
        )
    except Exception as e:
        await message.answer(f"Не получилось прочитать schedule.json: {e}", reply_markup=main_keyboard())


@dp.message(F.text == "Сегодня")
async def button_today(message: Message):
    await send_today_text(message)


@dp.message(F.text == "Завтра")
async def button_tomorrow(message: Message):
    await send_tomorrow_text(message)


@dp.message(F.text == "7 дней")
async def button_week(message: Message):
    await send_week_text(message)


@dp.message(F.text == "Обновить")
async def button_sync(message: Message):
    await sync(message)


@dp.message(F.text == "Источник")
async def button_source(message: Message):
    await source(message)


@dp.message(F.text == "Debug")
async def button_debug(message: Message):
    await debug(message)


async def main():
    global pool

    logging.info("Starting bot version: %s", VERSION)

    pool = await db.create_pool(config.database_url)
    await db.init_db(pool)

    try:
        count = await sync_fixtures(pool)
        logging.info("Initial local schedule sync complete. Matches: %s", count)
    except Exception:
        logging.exception("Initial sync failed")

    scheduler = setup_scheduler(bot, pool, config)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
