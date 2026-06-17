\
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from formatting import day_bounds_utc, format_matches, format_reminder, split_telegram_text
from local_schedule import load_matches


async def sync_fixtures(pool) -> int:
    matches = load_matches()
    return await db.replace_matches(pool, matches)


async def send_daily_schedule(bot, pool, tz):
    today = datetime.now(tz).date()
    start_utc, end_utc = day_bounds_utc(today, tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)

    text = format_matches("🏆 Матчи ЧМ сегодня", rows, tz)

    for chat_id in await db.get_active_chats(pool):
        for part in split_telegram_text(text):
            await bot.send_message(chat_id, part)


async def send_hour_reminders(bot, pool, tz):
    now = datetime.now(timezone.utc)
    start_utc = now + timedelta(minutes=55)
    end_utc = now + timedelta(minutes=65)

    rows = await db.get_upcoming_for_reminder(pool, start_utc, end_utc)
    chats = await db.get_active_chats(pool)

    for row in rows:
        for chat_id in chats:
            sent = await db.was_reminder_sent(pool, row["fixture_id"], chat_id, "one_hour")
            if sent:
                continue

            await bot.send_message(chat_id, format_reminder(row, tz))
            await db.mark_reminder_sent(pool, row["fixture_id"], chat_id, "one_hour")


def setup_scheduler(bot, pool, config) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.app_tz)

    scheduler.add_job(
        sync_fixtures,
        "interval",
        hours=12,
        args=[pool],
        id="sync_fixtures",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_daily_schedule,
        "cron",
        hour=config.daily_hour,
        minute=config.daily_minute,
        args=[bot, pool, config.app_tz],
        id="daily_schedule",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        send_hour_reminders,
        "interval",
        minutes=5,
        args=[bot, pool, config.app_tz],
        id="hour_reminders",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler
