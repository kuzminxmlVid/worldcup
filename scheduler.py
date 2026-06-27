from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
from api_football import ApiFootballError, fetch_score_for_match, fetch_scores_for_matches
from formatting import day_bounds_utc, format_matches, format_reminder, split_telegram_text
from keyboards import nav_inline_keyboard
from espn_schedule import fetch_world_cup_matches
from match_card import build_match_card


def _normalize_match_team(name: str) -> str:
    return str(name).strip().lower().replace("&", "and").replace("ё", "е")


def _same_match(existing, incoming) -> bool:
    existing_kickoff = existing["kickoff_utc"]
    incoming_kickoff = incoming["kickoff_utc"]

    # Keep existing fixture_id if the same match already exists in DB.
    # This preserves user predictions/expectations that are linked by fixture_id.
    time_diff = abs((existing_kickoff - incoming_kickoff).total_seconds()) / 3600
    if time_diff > 3:
        return False

    existing_home = _normalize_match_team(existing["home_team"])
    existing_away = _normalize_match_team(existing["away_team"])
    incoming_home = _normalize_match_team(incoming["home_team"])
    incoming_away = _normalize_match_team(incoming["away_team"])

    return existing_home == incoming_home and existing_away == incoming_away


def _preserve_existing_fixture_ids(matches: list[dict], existing_rows) -> list[dict]:
    existing_rows = list(existing_rows or [])
    used_existing_ids = set()
    result = []

    for match in matches:
        preserved_id = None

        for existing in existing_rows:
            existing_id = int(existing["fixture_id"])
            if existing_id in used_existing_ids:
                continue

            if _same_match(existing, match):
                preserved_id = existing_id
                used_existing_ids.add(existing_id)
                break

        if preserved_id is not None:
            # Keep the bot's old internal fixture_id, but store ESPN id in raw.
            raw = match.get("raw")
            try:
                import json
                raw_payload = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                raw_payload["espn_fixture_id"] = match["fixture_id"]
                match["raw"] = json.dumps(raw_payload, ensure_ascii=False)
            except Exception:
                pass
            match["fixture_id"] = preserved_id

        result.append(match)

    return result


async def sync_fixtures(pool) -> int:
    matches = await fetch_world_cup_matches()

    if not matches:
        logging.warning("External schedule sync returned zero matches. Keeping current DB unchanged.")
        return 0

    existing_rows = await db.get_all_matches(pool)
    matches = _preserve_existing_fixture_ids(matches, existing_rows)

    return await db.replace_matches(pool, matches)


async def sync_played_scores(pool) -> int:
    rows = await db.get_matches_for_score_backfill(pool)

    logging.info("Backfilling played match scores: rows=%s", len(rows))

    if not rows:
        return 0

    try:
        scores_by_fixture_id = await fetch_scores_for_matches(rows)
    except ApiFootballError:
        logging.exception("Played scores backfill failed")
        return 0
    except Exception:
        logging.exception("Unexpected played scores backfill error")
        return 0

    updated = 0

    for row in rows:
        fixture_id = row["fixture_id"]
        score = scores_by_fixture_id.get(fixture_id)
        if not score:
            logging.info(
                "No score found for fixture_id=%s %s - %s",
                fixture_id,
                row["home_team"],
                row["away_team"],
            )
            continue

        await db.update_match_score(
            pool,
            fixture_id=fixture_id,
            api_fixture_id=score.get("api_fixture_id"),
            status_short=score.get("status_short"),
            status_long=score.get("status_long"),
            home_goals=score.get("home_goals"),
            away_goals=score.get("away_goals"),
        )
        updated += 1

        logging.info(
            "Played score updated: fixture_id=%s %s %s:%s %s",
            fixture_id,
            row["home_team"],
            score.get("home_goals"),
            score.get("away_goals"),
            row["away_team"],
        )

    return updated


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
        sync_played_scores,
        "interval",
        minutes=30,
        args=[pool],
        id="sync_played_scores",
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
