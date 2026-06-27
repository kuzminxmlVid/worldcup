import asyncio
import logging
import re
from difflib import get_close_matches
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup

import db
from config import load_config
from formatting import (
    TEAM_FLAGS,
    NOTE_MAX_LEN,
    POST_THOUGHTS_MAX_LEN,
    PREDICTION_MAX_LEN,
    day_bounds_utc,
    format_matches,
    format_debug,
    format_alerts_status,
    format_user_match_data,
    format_note_too_long,
    format_post_thoughts_too_long,
    format_prediction_too_long,
    split_telegram_text,
    help_text,
)
from keyboards import main_keyboard, nav_inline_keyboard, match_inline_keyboard, match_list_keyboard
from match_card import build_match_card
from scheduler import setup_scheduler, sync_fixtures, sync_played_scores

VERSION = "external-espn-schedule-v26"

logging.basicConfig(level=logging.INFO)
config = load_config()
bot = Bot(token=config.bot_token)
dp = Dispatcher()
pool = None

REPLY_MARKER_RE = re.compile(r"Код:\s*(prediction|note|post_thoughts|team_search):(\d+):(\d+)")

TEAM_ALIASES = {
    "алжир": "Algeria",
    "аргентина": "Argentina",
    "австралия": "Australia",
    "австрия": "Austria",
    "бельгия": "Belgium",
    "босния": "Bosnia & Herzegovina",
    "босния и герцеговина": "Bosnia & Herzegovina",
    "бразилия": "Brazil",
    "канада": "Canada",
    "кабо верде": "Cape Verde",
    "кабо-верде": "Cape Verde",
    "колумбия": "Colombia",
    "хорватия": "Croatia",
    "кюрасао": "Curaçao",
    "чехия": "Czech Republic",
    "чешская республика": "Czech Republic",
    "др конго": "DR Congo",
    "д р конго": "DR Congo",
    "конго": "DR Congo",
    "демократическая республика конго": "DR Congo",
    "эквадор": "Ecuador",
    "египет": "Egypt",
    "англия": "England",
    "франция": "France",
    "германия": "Germany",
    "гана": "Ghana",
    "гаити": "Haiti",
    "иран": "Iran",
    "ирак": "Iraq",
    "кот д ивуар": "Ivory Coast",
    "кот-д'ивуар": "Ivory Coast",
    "кот-д’ивуар": "Ivory Coast",
    "япония": "Japan",
    "иордания": "Jordan",
    "мексика": "Mexico",
    "марокко": "Morocco",
    "нидерланды": "Netherlands",
    "голландия": "Netherlands",
    "новая зеландия": "New Zealand",
    "норвегия": "Norway",
    "панама": "Panama",
    "парагвай": "Paraguay",
    "португалия": "Portugal",
    "катар": "Qatar",
    "саудовская аравия": "Saudi Arabia",
    "саудовская": "Saudi Arabia",
    "шотландия": "Scotland",
    "сенегал": "Senegal",
    "юар": "South Africa",
    "южная африка": "South Africa",
    "южная корея": "South Korea",
    "корея": "South Korea",
    "испания": "Spain",
    "швеция": "Sweden",
    "швейцария": "Switzerland",
    "тунис": "Tunisia",
    "турция": "Turkey",
    "сша": "USA",
    "америка": "USA",
    "уругвай": "Uruguay",
    "узбекистан": "Uzbekistan",
}


def normalize_team_query(query: str) -> str:
    cleaned = " ".join(query.strip().lower().replace("ё", "е").split())
    return TEAM_ALIASES.get(cleaned, query.strip())


def team_slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def local_team_select_keyboard(team_names: list[str], team_flags: dict | None = None) -> InlineKeyboardMarkup:
    team_flags = team_flags or {}
    inline_keyboard = []
    row = []

    for name in team_names:
        label = f"{team_flags.get(name, '')} {name}".strip()
        row.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"team_select:{team_slug(name)}",
            )
        )

        if len(row) == 2:
            inline_keyboard.append(row)
            row = []

    if row:
        inline_keyboard.append(row)

    inline_keyboard.append([
        InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
        InlineKeyboardButton(text="Следующий", callback_data="nav:next"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



def user_id_from_message(message: Message) -> int:
    return message.from_user.id if message.from_user else message.chat.id


def match_has_started(row) -> bool:
    kickoff = row["kickoff_utc"]
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= kickoff.astimezone(timezone.utc)


def parse_reply_marker(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return None

    match = REPLY_MARKER_RE.search(message.reply_to_message.text)
    if not match:
        return None

    action = match.group(1)
    fixture_id = int(match.group(2))
    source_message_id = int(match.group(3))
    return {
        "action": action,
        "fixture_id": fixture_id,
        "source_message_id": source_message_id if source_message_id else None,
    }


async def reminders_enabled_for(chat_id: int) -> bool:
    settings = await db.get_chat_settings(pool, chat_id)
    return bool(settings["reminders_enabled"]) if settings else False


async def standings_context_for_match(row) -> dict:
    group_name = row["group_name"]
    if not group_name:
        return {}

    table = await db.get_group_standings(pool, group_name)
    return {item["team"]: item for item in table}


async def send_text(message: Message, text: str):
    enabled = await reminders_enabled_for(message.chat.id)
    parts = split_telegram_text(text)
    for i, part in enumerate(parts):
        markup = nav_inline_keyboard(enabled) if i == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


async def send_matches_with_buttons(message: Message, title: str, rows):
    enabled = await reminders_enabled_for(message.chat.id)
    text = format_matches(title, rows, config.app_tz)

    if not rows:
        await message.answer(text, reply_markup=nav_inline_keyboard(enabled))
        return

    parts = split_telegram_text(text)
    for i, part in enumerate(parts):
        markup = match_list_keyboard(rows, config.app_tz, enabled) if i == len(parts) - 1 else None
        await message.answer(part, reply_markup=markup)


async def send_today_text(message: Message):
    day = datetime.now(config.app_tz).date()
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_matches_with_buttons(message, "Матчи ЧМ сегодня", rows)


async def send_tomorrow_text(message: Message):
    day = datetime.now(config.app_tz).date() + timedelta(days=1)
    start_utc, end_utc = day_bounds_utc(day, config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_matches_with_buttons(message, "Матчи ЧМ завтра", rows)


async def send_week_text(message: Message):
    today_local = datetime.now(config.app_tz).date()
    start_utc, _ = day_bounds_utc(today_local, config.app_tz)
    _, end_utc = day_bounds_utc(today_local + timedelta(days=7), config.app_tz)
    rows = await db.get_matches_between(pool, start_utc, end_utc)
    await send_matches_with_buttons(message, "Матчи ЧМ на 7 дней", rows)


async def send_match_personal_post(
    message: Message,
    row,
    source_message_id: int | None = None,
    user_id: int | None = None,
):
    if not row:
        await message.answer("Не нашёл этот матч в базе. Попробуй /sync и потом /next.")
        return

    user_id = user_id or user_id_from_message(message)
    enabled = await reminders_enabled_for(message.chat.id)
    user_data = await db.get_user_match_data(pool, message.chat.id, user_id, row["fixture_id"])
    standings = await standings_context_for_match(row)
    text = format_user_match_data(row, user_data, config.app_tz, standings=standings)
    markup = match_inline_keyboard(
        fixture_id=row["fixture_id"],
        reminders_enabled=enabled,
        has_prediction=bool(user_data and user_data["prediction"]),
        has_note=bool(user_data and user_data["note"]),
        has_post_thoughts=bool(user_data and user_data["post_match_thoughts"]),
        prediction_locked=match_has_started(row),
    )

    if source_message_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=source_message_id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
            )
            return
        except Exception:
            logging.exception("Could not edit personal match post")

    await message.answer(text, reply_markup=markup, parse_mode="HTML")

async def send_match_by_id(message: Message, fixture_id: int, user_id: int | None = None):
    row = await db.get_match_by_id(pool, fixture_id)
    if not row:
        await message.answer("Не нашёл этот матч в базе. Попробуй /sync и потом /next.")
        return

    actual_user_id = user_id or user_id_from_message(message)

    standings = await standings_context_for_match(row)
    card_path = build_match_card(row, config.app_tz, standings=standings)
    try:
        sent_card = await message.answer_photo(FSInputFile(card_path), caption="Карточка матча")
        await db.save_match_card_message(
            pool,
            message.chat.id,
            actual_user_id,
            row["fixture_id"],
            sent_card.message_id,
        )
    finally:
        try:
            Path(card_path).unlink(missing_ok=True)
        except Exception:
            pass

    await send_match_personal_post(message, row, user_id=actual_user_id)


async def send_next_match_text(message: Message, user_id: int | None = None):
    row = await db.get_next_match(pool)
    if not row:
        enabled = await reminders_enabled_for(message.chat.id)
        await message.answer("Ближайших матчей после текущего времени нет.", reply_markup=nav_inline_keyboard(enabled))
        return
    await send_match_by_id(message, row["fixture_id"], user_id=user_id)


async def send_source_text(message: Message):
    enabled = await reminders_enabled_for(message.chat.id)
    count, first_row, last_row, next_rows = await db.get_debug_stats(pool)

    lines = [
        "Источник расписания: ESPN public scoreboard",
        "URL: site.api.espn.com / soccer / fifa.world / scoreboard",
        f"Версия кода: {VERSION}",
        f"Матчей в базе: {count}",
    ]

    if first_row:
        lines.append(f"Первый матч: {first_row['kickoff_utc'].astimezone(config.app_tz).strftime('%d.%m.%Y %H:%M')}")
    if last_row:
        lines.append(f"Последний матч: {last_row['kickoff_utc'].astimezone(config.app_tz).strftime('%d.%m.%Y %H:%M')}")

    await message.answer("\n".join(lines), reply_markup=nav_inline_keyboard(enabled))

async def send_debug_text(message: Message):
    enabled = await reminders_enabled_for(message.chat.id)
    count, first_row, last_row, next_rows = await db.get_debug_stats(pool)
    await message.answer(format_debug(count, first_row, last_row, next_rows, config.app_tz), reply_markup=nav_inline_keyboard(enabled))


async def toggle_alerts(message: Message):
    new_value = await db.toggle_reminders(pool, message.chat.id)
    await message.answer(format_alerts_status(new_value), reply_markup=nav_inline_keyboard(new_value))



async def send_team_picker(message: Message):
    names = await db.get_all_team_names(pool)

    if not names:
        await message.answer(
            "Команд пока нет в базе. Нажми /sync, а потом попробуй снова.",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        "Выбери сборную. Я покажу все её матчи: сыгранные и будущие.",
        reply_markup=local_team_select_keyboard(names, TEAM_FLAGS),
    )


async def prompt_team_search(message: Message, user_id: int):
    await db.set_pending_input(pool, message.chat.id, user_id, 0, "team_search", None)
    logging.info(
        "Pending input set: chat_id=%s user_id=%s action=team_search",
        message.chat.id,
        user_id,
    )

    await message.answer(
        "Напиши название сборной одним сообщением.\n\n"
        "Например: Португалия, Brazil, USA, Конго.\n"
        "Я покажу все матчи этой команды: сыгранные и будущие.\n\n"
        "Код: team_search:0:0",
        reply_markup=ForceReply(selective=True, input_field_placeholder="Название команды"),
    )


async def send_team_search_results(message: Message, query: str):
    raw_query = query.strip()

    if len(raw_query) < 2:
        await message.answer("Слишком короткий запрос. Напиши хотя бы 2 символа.")
        return

    normalized = normalize_team_query(raw_query)
    rows = await db.search_matches_by_team(pool, normalized)

    if rows:
        title = f"Матчи команды: {normalized}"
        await send_matches_with_buttons(message, title, rows)
        return

    names = await db.get_all_team_names(pool)
    suggestions = get_close_matches(normalized, names, n=6, cutoff=0.25)

    if suggestions:
        await message.answer(
            "Матчи не нашёл.\n\n"
            "Возможно, ты имел в виду:\n"
            + "\n".join(f"• {name}" for name in suggestions)
            + "\n\nНажми «Команды» или /team и попробуй ещё раз.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "Матчи по этой команде не нашёл.\n\n"
            "Попробуй написать название на английском, например: Portugal, Brazil, USA.",
            reply_markup=main_keyboard(),
        )

async def prompt_prediction(message: Message, fixture_id: int, user_id: int, source_message_id: int | None = None):
    row = await db.get_match_by_id(pool, fixture_id)
    if not row:
        await message.answer("Не нашёл этот матч в базе.")
        return

    if match_has_started(row):
        await message.answer("Прогноз уже закрыт. Матч начался, поэтому прогноз изменить нельзя.")
        return

    await db.set_pending_input(pool, message.chat.id, user_id, fixture_id, "prediction", source_message_id)
    logging.info(
        "Pending input set: chat_id=%s user_id=%s fixture_id=%s action=prediction source_message_id=%s",
        message.chat.id,
        user_id,
        fixture_id,
        source_message_id,
    )

    marker = f"prediction:{fixture_id}:{source_message_id or 0}"
    await message.answer(
        "Пришли прогноз одним сообщением.\n\n"
        "Например: 2:1 или Portugal 2:1 DR Congo.\n"
        f"Максимум: {PREDICTION_MAX_LEN} символов.\n\n"
        f"Код: {marker}",
        reply_markup=ForceReply(selective=True, input_field_placeholder="Напиши прогноз"),
    )


async def prompt_note(message: Message, fixture_id: int, user_id: int, source_message_id: int | None = None):
    row = await db.get_match_by_id(pool, fixture_id)
    if not row:
        await message.answer("Не нашёл этот матч в базе.")
        return

    await db.set_pending_input(pool, message.chat.id, user_id, fixture_id, "note", source_message_id)
    logging.info(
        "Pending input set: chat_id=%s user_id=%s fixture_id=%s action=note source_message_id=%s",
        message.chat.id,
        user_id,
        fixture_id,
        source_message_id,
    )

    marker = f"note:{fixture_id}:{source_message_id or 0}"
    await message.answer(
        "Пришли ожидания от матча одним сообщением.\n\n"
        f"Максимум: {NOTE_MAX_LEN} символов.\n"
        "Если текст будет длиннее, я не сохраню его и попрошу сократить.\n\n"
        f"Код: {marker}",
        reply_markup=ForceReply(selective=True, input_field_placeholder="Ожидания от матча"),
    )


async def prompt_post_thoughts(message: Message, fixture_id: int, user_id: int, source_message_id: int | None = None):
    row = await db.get_match_by_id(pool, fixture_id)
    if not row:
        await message.answer("Не нашёл этот матч в базе.")
        return

    await db.set_pending_input(pool, message.chat.id, user_id, fixture_id, "post_thoughts", source_message_id)
    logging.info(
        "Pending input set: chat_id=%s user_id=%s fixture_id=%s action=post_thoughts source_message_id=%s",
        message.chat.id,
        user_id,
        fixture_id,
        source_message_id,
    )

    marker = f"post_thoughts:{fixture_id}:{source_message_id or 0}"
    await message.answer(
        "Пришли мысли после матча одним сообщением.\n\n"
        f"Максимум: {POST_THOUGHTS_MAX_LEN} символов.\n"
        "Если текст будет длиннее, я не сохраню его и попрошу сократить.\n\n"
        f"Код: {marker}",
        reply_markup=ForceReply(selective=True, input_field_placeholder="Мысли после матча"),
    )

async def handle_pending_text(message: Message) -> bool:
    if not message.text:
        return False

    user_id = user_id_from_message(message)
    pending = await db.get_pending_input(pool, message.chat.id, user_id)
    reply_marker = None

    if pending:
        fixture_id = int(pending["fixture_id"])
        action = pending["action"]
        source_message_id = pending["source_message_id"]
        logging.info(
            "Pending input found in DB: chat_id=%s user_id=%s fixture_id=%s action=%s source_message_id=%s",
            message.chat.id,
            user_id,
            fixture_id,
            action,
            source_message_id,
        )
    else:
        reply_marker = parse_reply_marker(message)
        if not reply_marker:
            logging.info("No pending input found: chat_id=%s user_id=%s", message.chat.id, user_id)
            return False

        fixture_id = reply_marker["fixture_id"]
        action = reply_marker["action"]
        source_message_id = reply_marker["source_message_id"]
        logging.info(
            "Pending input recovered from reply marker: chat_id=%s user_id=%s fixture_id=%s action=%s source_message_id=%s",
            message.chat.id,
            user_id,
            fixture_id,
            action,
            source_message_id,
        )

    text = message.text.strip()

    if action == "team_search":
        await db.clear_pending_input(pool, message.chat.id, user_id)
        await send_team_search_results(message, text)
        return True

    if action == "prediction":
        if not text:
            await message.answer("Пустой прогноз не сохраняю. Пришли прогноз текстом.")
            return True
        if len(text) > PREDICTION_MAX_LEN:
            await message.answer(format_prediction_too_long(len(text)))
            return True

        row = await db.get_match_by_id(pool, fixture_id)
        if row and match_has_started(row):
            await db.clear_pending_input(pool, message.chat.id, user_id)
            await message.answer("Прогноз уже закрыт. Матч начался, поэтому прогноз не сохранён.")
            await send_match_personal_post(message, row, source_message_id, user_id=user_id)
            return True

        await db.save_prediction(pool, message.chat.id, user_id, fixture_id, text)
        await db.clear_pending_input(pool, message.chat.id, user_id)
        row = await db.get_match_by_id(pool, fixture_id)
        await send_match_personal_post(message, row, source_message_id, user_id=user_id)
        return True

    if action == "note":
        if not text:
            await message.answer("Пустые ожидания не сохраняю. Пришли текстом.")
            return True
        if len(text) > NOTE_MAX_LEN:
            await message.answer(format_note_too_long(len(text)))
            return True

        await db.save_note(pool, message.chat.id, user_id, fixture_id, text)
        await db.clear_pending_input(pool, message.chat.id, user_id)
        row = await db.get_match_by_id(pool, fixture_id)
        await send_match_personal_post(message, row, source_message_id, user_id=user_id)
        return True

    if action == "post_thoughts":
        if not text:
            await message.answer("Пустые мысли после матча не сохраняю. Пришли текстом.")
            return True
        if len(text) > POST_THOUGHTS_MAX_LEN:
            await message.answer(format_post_thoughts_too_long(len(text)))
            return True

        await db.save_post_match_thoughts(pool, message.chat.id, user_id, fixture_id, text)
        await db.clear_pending_input(pool, message.chat.id, user_id)
        row = await db.get_match_by_id(pool, fixture_id)
        await send_match_personal_post(message, row, source_message_id, user_id=user_id)
        return True

    await db.clear_pending_input(pool, message.chat.id, user_id)
    return False


@dp.message(Command("start"))
async def start(message: Message):
    await db.add_chat(pool, message.chat.id)
    enabled = await reminders_enabled_for(message.chat.id)
    await message.answer("Готово. Бот запущен.\n\n" + help_text(enabled), reply_markup=main_keyboard())


@dp.message(Command("menu"))
@dp.message(F.text == "Меню")
async def menu(message: Message):
    enabled = await reminders_enabled_for(message.chat.id)
    await message.answer(help_text(enabled), reply_markup=main_keyboard())




@dp.message(Command("match"))
async def match_by_command(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Напиши так: /match 123")
        return

    await send_match_by_id(message, int(parts[1].strip()), user_id=user_id_from_message(message))


@dp.message(F.text.regexp(r"^/match_\d+(?:@\w+)?$"))
async def match_by_short_link(message: Message):
    text = (message.text or "").split("@", 1)[0]
    fixture_id = int(text.replace("/match_", ""))
    await send_match_by_id(message, fixture_id, user_id=user_id_from_message(message))


@dp.message(Command("team"))
@dp.message(Command("teams"))
@dp.message(Command("search"))
@dp.message(F.text == "Команды")
async def team_search(message: Message):
    await send_team_picker(message)




@dp.message(Command("clear"))
async def clear_last_match_data(message: Message):
    user_id = user_id_from_message(message)
    row = await db.get_last_match_for_user(pool, message.chat.id, user_id)
    if not row:
        await message.answer("Не нашёл последний открытый матч. Открой матч и потом нажми /clear.")
        return

    await db.clear_user_match_data(pool, message.chat.id, user_id, row["fixture_id"])
    await db.clear_pending_input(pool, message.chat.id, user_id)
    await send_match_personal_post(message, row, user_id=user_id)


@dp.message(Command("alerts"))
@dp.message(F.text == "Автопост")
async def alerts_toggle(message: Message):
    await toggle_alerts(message)


@dp.message(Command("alerts_on"))
async def alerts_on(message: Message):
    await db.set_reminders_enabled(pool, message.chat.id, True)
    await message.answer(format_alerts_status(True), reply_markup=nav_inline_keyboard(True))


@dp.message(Command("alerts_off"))
async def alerts_off(message: Message):
    await db.set_reminders_enabled(pool, message.chat.id, False)
    await message.answer(format_alerts_status(False), reply_markup=nav_inline_keyboard(False))


@dp.message(Command("stop"))
async def stop(message: Message):
    await db.stop_chat(pool, message.chat.id)
    await message.answer("Ок, больше не буду присылать расписание в этот чат.")


@dp.message(Command("sync"))
async def sync(message: Message):
    enabled = await reminders_enabled_for(message.chat.id)
    await message.answer("Обновляю расписание из открытого источника ESPN...")
    try:
        count = await sync_fixtures(pool)
        await message.answer(f"Готово. Загружено матчей: {count}.", reply_markup=nav_inline_keyboard(enabled))
    except Exception as e:
        logging.exception("Sync failed")
        await message.answer(f"Не получилось обновить расписание: {e}", reply_markup=nav_inline_keyboard(enabled))


@dp.message(Command("sync_scores"))
async def sync_scores(message: Message):
    await message.answer("Обновляю счёт сыгранных матчей...")
    try:
        updated = await sync_played_scores(pool)
        await message.answer(f"Готово. Обновлено матчей: {updated}.")
    except Exception as e:
        logging.exception("Scores sync failed")
        await message.answer(f"Не получилось обновить счёт: {e}")


@dp.message(Command("today"))
async def today(message: Message):
    await send_today_text(message)


@dp.message(Command("tomorrow"))
async def tomorrow(message: Message):
    await send_tomorrow_text(message)


@dp.message(Command("week"))
async def week(message: Message):
    await send_week_text(message)


@dp.message(Command("next"))
async def next_match(message: Message):
    await send_next_match_text(message)


@dp.message(Command("debug"))
async def debug(message: Message):
    await send_debug_text(message)


@dp.message(Command("source"))
async def source(message: Message):
    await send_source_text(message)


@dp.message(F.text == "Сегодня")
async def button_today(message: Message):
    await send_today_text(message)


@dp.message(F.text == "Завтра")
async def button_tomorrow(message: Message):
    await send_tomorrow_text(message)


@dp.message(F.text == "Следующий матч")
async def button_next_match(message: Message):
    await send_next_match_text(message)


@dp.message(F.text == "7 дней")
async def button_week(message: Message):
    await send_week_text(message)


@dp.message(F.text == "Обновить")
async def button_sync(message: Message):
    await sync(message)


@dp.callback_query(F.data.startswith("nav:"))
async def nav_callback(callback: CallbackQuery):
    action = callback.data.split(":", 1)[1]
    await callback.answer()
    if action == "today":
        await send_today_text(callback.message)
    elif action == "tomorrow":
        await send_tomorrow_text(callback.message)
    elif action == "next":
        await send_next_match_text(callback.message, user_id=callback.from_user.id)
    elif action == "week":
        await send_week_text(callback.message)
    elif action == "teams":
        await send_team_picker(callback.message)
    elif action == "team_search":
        await prompt_team_search(callback.message, callback.from_user.id)
    elif action == "sync":
        await sync(callback.message)
    elif action == "menu":
        await menu(callback.message)
    elif action == "alerts_toggle":
        await toggle_alerts(callback.message)




@dp.callback_query(F.data.startswith("team_select:"))
async def team_select_callback(callback: CallbackQuery):
    selected_slug = callback.data.split(":", 1)[1]
    names = await db.get_all_team_names(pool)

    team_name = None
    for name in names:
        if team_slug(name) == selected_slug:
            team_name = name
            break

    if not team_name:
        await callback.answer("Не нашёл команду.")
        return

    await callback.answer(team_name)
    await send_team_search_results(callback.message, team_name)


@dp.callback_query(F.data.startswith("open_match:"))
async def open_match_callback(callback: CallbackQuery):
    try:
        fixture_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Не понял матч.")
        return

    await callback.answer()
    await send_match_by_id(callback.message, fixture_id, user_id=callback.from_user.id)


@dp.callback_query(F.data.startswith("match:"))
async def match_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Не понял действие.")
        return

    action = parts[1]
    fixture_id = int(parts[2])
    source_message_id = callback.message.message_id if callback.message else None
    user_id = callback.from_user.id
    await callback.answer()

    if action == "prediction":
        await prompt_prediction(callback.message, fixture_id, user_id, source_message_id)
    elif action == "prediction_locked":
        await callback.message.answer("Прогноз закрыт. Матч уже начался.")
    elif action == "note":
        await prompt_note(callback.message, fixture_id, user_id, source_message_id)
    elif action == "post_thoughts":
        await prompt_post_thoughts(callback.message, fixture_id, user_id, source_message_id)
    elif action == "score":
        await callback.message.answer("Счёт обновляется автоматически после матча и появится скрытым текстом в посте с твоими данными.")
    elif action == "show":
        row = await db.get_match_by_id(pool, fixture_id)
        if row:
            await send_match_personal_post(callback.message, row, source_message_id, user_id=user_id)
        else:
            await callback.message.answer("Не нашёл этот матч в базе.")
    elif action == "clear":
        await db.clear_user_match_data(pool, callback.message.chat.id, user_id, fixture_id)
        await db.clear_pending_input(pool, callback.message.chat.id, user_id)
        row = await db.get_match_by_id(pool, fixture_id)
        if row:
            await send_match_personal_post(callback.message, row, source_message_id, user_id=user_id)


@dp.message(F.text)
async def pending_or_unknown_text(message: Message):
    handled = await handle_pending_text(message)
    if handled:
        return

    text = (message.text or "").strip()

    match_link = re.match(r"^/match_(\d+)(?:@\w+)?$", text)
    if match_link:
        await send_match_by_id(message, int(match_link.group(1)), user_id=user_id_from_message(message))
        return

    if text.startswith("/"):
        await message.answer("Не понял команду. Выбери действие кнопками снизу или нажми /menu.", reply_markup=main_keyboard())
        return

    # Fallback: any free text is treated as a team search.
    # This protects the UX if Telegram ForceReply is ignored or pending_inputs was lost
    # after a deploy/restart.
    if len(text) >= 2:
        logging.info(
            "Fallback team search from free text: chat_id=%s user_id=%s query=%s",
            message.chat.id,
            user_id_from_message(message),
            text,
        )
        await send_team_search_results(message, text)
        return

    await message.answer("Не понял команду. Выбери действие кнопками снизу или нажми /menu.", reply_markup=main_keyboard())


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

    try:
        updated_scores = await sync_played_scores(pool)
        logging.info("Initial played scores sync complete. Updated: %s", updated_scores)
    except Exception:
        logging.exception("Initial played scores sync failed")

    scheduler = setup_scheduler(bot, pool, config)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
