from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from api_football import ApiFootballError, fetch_score_for_match
from formatting import day_bounds_utc, format_matches, format_reminder, split_telegram_text
from keyboards import nav_inline_keyboard
from local_schedule import load_matches
from match_card import build_match_card


async def sync_fixtures(pool) -> int:
    matches = load_matches()
    return await db.replace_matches(pool, matches)


async def sync_recent_scores(pool) -> None:
    now = datetime.now(timezone.utc)

    # Update matches that are likely live or recently finished.
    # The score itself is shown only as Telegram spoiler text in the personal match post.
    start_utc = now - timedelta(hours=4)
    end_utc = now + timedelta(minutes=30)

    rows = await db.get_matches_for_score_update(pool, start_utc, end_utc)

    logging.info(
        "Checking match scores: rows=%s start_utc=%s end_utc=%s",
        len(rows),
        start_utc,
        end_utc,
    )

    for row in rows:
        try:
            score = await fetch_score_for_match(row)
            await db.update_match_score(
                pool,
                fixture_id=row["fixture_id"],
                api_fixture_id=score.get("api_fixture_id"),
                status_short=score.get("status_short"),
                status_long=score.get("status_long"),
                home_goals=score.get("home_goals"),
                away_goals=score.get("away_goals"),
            )
            logging.info(
                "Score updated: fixture_id=%s %s %s:%s %s",
                row["fixture_id"],
                row["home_team"],
                score.get("home_goals"),
                score.get("away_goals"),
                row["away_team"],
            )
        except ApiFootballError:
            logging.exception(
                "Score update skipped: fixture_id=%s %s - %s",
                row["fixture_id"],
                row["home_team"],
                row["away_team"],
            )
        except Exception:
            logging.exception(
                "Unexpected score update error: fixture_id=%s %s - %s",
                row["fixture_id"],
                row["home_team"],
                row["away_team"],
            )


async def send_daily_schedule(bot, pool, tz):
    today = datetime.now(tz).date()
    start_utc, end_utc = day_bounds_utc(today, tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)

    text = format_matches("Матчи ЧМ сегодня", rows, tz)

    for chat_id in await db.get_active_chats(pool):
        try:
            settings = await db.get_chat_settings(pool, chat_id)
            enabled = bool(settings["reminders_enabled"]) if settings else False
            parts = split_telegram_text(text)
            for i, part in enumerate(parts):
                markup = nav_inline_keyboard(enabled) if i == len(parts) - 1 else None
                await bot.send_message(chat_id, part, reply_markup=markup)
        except Exception:
            logging.exception("Failed to send daily schedule: chat_id=%s", chat_id)


async def send_hour_reminders(bot, pool, tz):
    now = datetime.now(timezone.utc)

    start_utc = now + timedelta(minutes=50)
    end_utc = now + timedelta(minutes=70)

    rows = await db.get_upcoming_for_reminder(pool, start_utc, end_utc)
    chats = await db.get_active_reminder_chats(pool)

    logging.info(
        "Checking hour reminders: rows=%s chats=%s start_utc=%s end_utc=%s",
        len(rows),
        len(chats),
        start_utc,
        end_utc,
    )

    for row in rows:
        for chat_id in chats:
            sent = await db.was_reminder_sent(pool, row["fixture_id"], chat_id, "one_hour")
            if sent:
                continue

            card_path = None
            try:
                caption = format_reminder(row, tz)
                card_path = build_match_card(row, tz)

                await bot.send_photo(
                    chat_id,
                    FSInputFile(card_path),
                    caption=caption,
                    reply_markup=nav_inline_keyboard(True),
                )

                await db.mark_reminder_sent(pool, row["fixture_id"], chat_id, "one_hour")
                logging.info(
                    "Hour reminder sent: chat_id=%s fixture_id=%s %s - %s",
                    chat_id,
                    row["fixture_id"],
                    row["home_team"],
                    row["away_team"],
                )

            except Exception:
                logging.exception(
                    "Failed to send hour reminder: chat_id=%s fixture_id=%s %s - %s",
                    chat_id,
                    row["fixture_id"],
                    row["home_team"],
                    row["away_team"],
                )

            finally:
                if card_path:
                    try:
                        Path(card_path).unlink(missing_ok=True)
                    except Exception:
                        pass


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
        sync_recent_scores,
        "interval",
        minutes=15,
        args=[pool],
        id="sync_recent_scores",
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
