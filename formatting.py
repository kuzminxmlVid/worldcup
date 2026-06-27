from collections import OrderedDict
from datetime import datetime, time, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

TEAM_FLAGS = {
    "Algeria": "🇩🇿",
    "Argentina": "🇦🇷",
    "Australia": "🇦🇺",
    "Austria": "🇦🇹",
    "Belgium": "🇧🇪",
    "Bosnia & Herzegovina": "🇧🇦",
    "Brazil": "🇧🇷",
    "Canada": "🇨🇦",
    "Cape Verde": "🇨🇻",
    "Colombia": "🇨🇴",
    "Croatia": "🇭🇷",
    "Curaçao": "🇨🇼",
    "Czech Republic": "🇨🇿",
    "DR Congo": "🇨🇩",
    "Ecuador": "🇪🇨",
    "Egypt": "🇪🇬",
    "England": "🏴",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "Ghana": "🇬🇭",
    "Haiti": "🇭🇹",
    "Iran": "🇮🇷",
    "Iraq": "🇮🇶",
    "Ivory Coast": "🇨🇮",
    "Japan": "🇯🇵",
    "Jordan": "🇯🇴",
    "Mexico": "🇲🇽",
    "Morocco": "🇲🇦",
    "Netherlands": "🇳🇱",
    "New Zealand": "🇳🇿",
    "Norway": "🇳🇴",
    "Panama": "🇵🇦",
    "Paraguay": "🇵🇾",
    "Portugal": "🇵🇹",
    "Qatar": "🇶🇦",
    "Saudi Arabia": "🇸🇦",
    "Scotland": "🏴",
    "Senegal": "🇸🇳",
    "South Africa": "🇿🇦",
    "South Korea": "🇰🇷",
    "Spain": "🇪🇸",
    "Sweden": "🇸🇪",
    "Switzerland": "🇨🇭",
    "Tunisia": "🇹🇳",
    "Turkey": "🇹🇷",
    "USA": "🇺🇸",
    "Uruguay": "🇺🇾",
    "Uzbekistan": "🇺🇿",
}

GROUP_ICONS = {
    "Группа A": "A",
    "Группа B": "B",
    "Группа C": "C",
    "Группа D": "D",
    "Группа E": "E",
    "Группа F": "F",
    "Группа G": "G",
    "Группа H": "H",
    "Группа I": "I",
    "Группа J": "J",
    "Группа K": "K",
    "Группа L": "L",
}

EXPECTATION_MAX_LEN = 1500
NOTE_MAX_LEN = EXPECTATION_MAX_LEN  # legacy import name
POST_THOUGHTS_MAX_LEN = 1500
PREDICTION_MAX_LEN = 200


def day_bounds_utc(day, tz: ZoneInfo):
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def team_with_flag(name: str) -> str:
    return f"{TEAM_FLAGS.get(name, '🏳️')} {name}"


def team_with_flag_html(name: str) -> str:
    return f"{TEAM_FLAGS.get(name, '🏳️')} {escape(str(name))}"


def stage_with_icon(group_or_round: str) -> str:
    if not group_or_round:
        return "Стадия не указана"
    letter = GROUP_ICONS.get(group_or_round)
    if letter:
        return f"Группа {letter}"
    return str(group_or_round)


def _score_spoiler(row) -> str | None:
    home_goals = row["home_goals"]
    away_goals = row["away_goals"]
    if home_goals is None or away_goals is None:
        return None

    home = escape(str(row["home_team"]))
    away = escape(str(row["away_team"]))
    status = row["status_long"] or row["status_short"] or ""
    status_part = f" · {escape(str(status))}" if status else ""
    return f'<tg-spoiler>{home} {home_goals}:{away_goals} {away}{status_part}</tg-spoiler>'


def match_line(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    lines = [
        f"Время {kickoff.strftime('%H:%M')}",
        f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}",
        stage_with_icon(group_or_round),
        f"Карточка: /match_{row['fixture_id']}",
    ]

    if row["venue"]:
        lines.append(f"Стадион {row['venue']}")

    return "\n".join(lines)


def format_single_match(row, tz: ZoneInfo, title: str = "Следующий матч ЧМ") -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    lines = [
        title,
        "",
        f"Дата {kickoff.strftime('%d.%m.%Y')}",
        f"Время {kickoff.strftime('%H:%M')}",
        "",
        f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}",
        stage_with_icon(group_or_round),
    ]

    if row["venue"]:
        lines.append(f"Стадион {row['venue']}")

    return "\n".join(lines)


def _standing_line(team: str, standings: dict | None) -> str | None:
    if not standings:
        return None

    stats = standings.get(team)
    if not stats:
        return None

    points = int(stats.get("points", 0))
    played = int(stats.get("played", 0))
    rank = int(stats.get("rank", 0))

    return (
        f"{team_with_flag_html(team)}: "
        f"{rank} место, {points} очк., {played} игр"
    )


def format_user_match_data(row, user_data, tz: ZoneInfo, standings: dict | None = None) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)

    prediction = None
    expectations = None
    post_thoughts = None

    if user_data:
        prediction = user_data["prediction"]
        expectations = user_data["note"]
        try:
            post_thoughts = user_data["post_match_thoughts"]
        except Exception:
            post_thoughts = None

    lines = [
        "Мои данные по матчу",
        "",
        f"Дата {kickoff.strftime('%d.%m.%Y')}",
        f"Время {kickoff.strftime('%H:%M')}",
        f"{team_with_flag_html(row['home_team'])} — {team_with_flag_html(row['away_team'])}",
    ]

    home_standing = _standing_line(row["home_team"], standings)
    away_standing = _standing_line(row["away_team"], standings)

    if home_standing or away_standing:
        lines.extend(["", "Положение в группе:"])
        if home_standing:
            lines.append(home_standing)
        if away_standing:
            lines.append(away_standing)

    hidden_score = _score_spoiler(row)
    if hidden_score:
        lines.extend(["", "Счёт:", hidden_score])

    lines.extend([
        "",
        "Прогноз:",
        escape(str(prediction)) if prediction else "Пока не указан.",
        "",
        "Ожидания от матча:",
        escape(str(expectations)) if expectations else "Пока не добавлены.",
        "",
        "Мысли после матча:",
        escape(str(post_thoughts)) if post_thoughts else "Пока не добавлены.",
    ])

    return "\n".join(lines)

def format_matches(title: str, rows, tz: ZoneInfo) -> str:
    if not rows:
        return f"{title}\n\nМатчей нет."

    grouped = OrderedDict()
    for row in rows:
        key = row["kickoff_utc"].astimezone(tz).date()
        grouped.setdefault(key, []).append(row)

    parts = [title]
    for day, day_rows in grouped.items():
        parts.append(f"Дата {day.strftime('%d.%m.%Y')}")
        for row in day_rows:
            parts.append(match_line(row, tz))
    return "\n\n".join(parts)


def format_reminder(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    lines = [
        "Через час матч ЧМ",
        f"Время {kickoff.strftime('%d.%m, %H:%M')}",
        f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}",
        stage_with_icon(group_or_round),
    ]
    if row["venue"]:
        lines.append(f"Стадион {row['venue']}")
    return "\n".join(lines)


def format_debug(count, first_row, last_row, next_rows, tz: ZoneInfo) -> str:
    lines = ["Debug", f"Матчей в базе: {count}"]

    if first_row:
        lines.append(f"Первый матч: {first_row['kickoff_utc'].astimezone(tz).strftime('%d.%m.%Y %H:%M')}")
    if last_row:
        lines.append(f"Последний матч: {last_row['kickoff_utc'].astimezone(tz).strftime('%d.%m.%Y %H:%M')}")

    lines.append("")
    if next_rows:
        lines.append("Ближайшие матчи:")
        for row in next_rows:
            kickoff = row["kickoff_utc"].astimezone(tz).strftime("%d.%m %H:%M")
            lines.append(f"{kickoff} — {team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}")
    else:
        lines.append("Ближайших матчей после текущего времени нет.")

    return "\n".join(lines)


def format_alerts_status(enabled: bool) -> str:
    if enabled:
        return "Автопост за час до матча включён. Я буду присылать карточку ближайшего матча автоматически."
    return "Автопост за час до матча выключен. Автоматические карточки приходить не будут."


def format_expectation_too_long(length: int) -> str:
    return (
        f"Ожидания слишком длинные: {length} символов.\n\n"
        f"Максимум: {EXPECTATION_MAX_LEN} символов.\n"
        "Сократи текст и пришли ещё раз. Я пока ничего не сохранил."
    )


def format_note_too_long(length: int) -> str:
    return format_expectation_too_long(length)


def format_post_thoughts_too_long(length: int) -> str:
    return (
        f"Мысли после матча слишком длинные: {length} символов.\n\n"
        f"Максимум: {POST_THOUGHTS_MAX_LEN} символов.\n"
        "Сократи текст и пришли ещё раз. Я пока ничего не сохранил."
    )


def format_prediction_too_long(length: int) -> str:
    return (
        f"Прогноз слишком длинный: {length} символов.\n\n"
        f"Максимум: {PREDICTION_MAX_LEN} символов.\n"
        "Пришли короткий прогноз, например: 2:1 или Portugal 2:1 DR Congo."
    )


def help_text(reminders_enabled: bool | None = True) -> str:
    status = "включён" if reminders_enabled else "выключен"
    return (
        "Что умею:\n"
        "• Сегодня\n"
        "• Завтра\n"
        "• Следующий матч с карточкой\n"
        "• Поиск матчей по команде через /team или /search\n"
        "• Личный прогноз на матч\n"
        "• Ожидания от матча до 1500 символов\n"
        "• Мысли после матча до 1500 символов\n"
        "• Расписание на 7 дней\n"
        "• Автопост за час до матча через /alerts\n"
        "• Очистка данных последнего открытого матча через /clear\n\n"
        f"Сейчас автопост: {status}.\n"
        "Команды: /today /tomorrow /next /week /team /teams /search /alerts /clear /sync"
    )


def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts = []
    current = ""

    for block in text.split("\n\n"):
        piece = block if not current else "\n\n" + block
        if len(current) + len(piece) > limit:
            if current:
                parts.append(current)
            current = block
        else:
            current += piece

    if current:
        parts.append(current)

    return parts



def _playoff_round_key(row) -> tuple[int, str]:
    name = str(row["round_name"] or "").lower()

    if "1/16" in name or "round of 32" in name:
        return (1, "1/16 финала")
    if "1/8" in name or "round of 16" in name:
        return (2, "1/8 финала")
    if "1/4" in name or "quarter" in name:
        return (3, "1/4 финала")
    if "1/2" in name or "semi" in name:
        return (4, "1/2 финала")
    if "3" in name and "мест" in name or "third" in name:
        return (5, "Матч за 3-е место")
    if "финал" in name or "final" in name:
        return (6, "Финал")

    # Date fallback: keeps unknown external stages in a reasonable order.
    return (99, row["round_name"] or "Плей-офф")


def format_playoff_matches(rows, tz: ZoneInfo) -> str:
    if not rows:
        return (
            "Плей-офф ЧМ\n\n"
            "Матчей плей-офф пока нет в базе.\n\n"
            "Нажми /sync позже: пары появятся, когда внешний источник опубликует их."
        )

    grouped = OrderedDict()
    for row in rows:
        _, label = _playoff_round_key(row)
        grouped.setdefault(label, []).append(row)

    # Keep groups ordered by first match date, then by playoff stage key.
    ordered_labels = sorted(
        grouped.keys(),
        key=lambda label: (
            min(item["kickoff_utc"] for item in grouped[label]),
            min(_playoff_round_key(item)[0] for item in grouped[label]),
        ),
    )

    parts = ["Плей-офф ЧМ"]

    for label in ordered_labels:
        parts.append(label)

        for row in grouped[label]:
            kickoff = row["kickoff_utc"].astimezone(tz)
            score = ""
            if row["home_goals"] is not None and row["away_goals"] is not None:
                score = f"  •  {row['home_goals']}:{row['away_goals']}"

            lines = [
                f"{kickoff.strftime('%d.%m.%Y %H:%M')}",
                f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}{score}",
            ]

            if row["venue"]:
                lines.append(f"Стадион {row['venue']}")

            lines.append(f"Карточка: /match_{row['fixture_id']}")
            parts.append("\n".join(lines))

    return "\n\n".join(parts)



def format_next_round_matches(round_label: str | None, rows, tz: ZoneInfo) -> str:
    if not rows:
        return (
            "Следующий раунд\n\n"
            "Матчей следующего раунда пока нет в базе.\n\n"
            "Нажми /sync позже: пары появятся, когда внешний источник их опубликует."
        )

    title = f"Следующий раунд: {round_label or 'Плей-офф'}"
    parts = [title]

    for index, row in enumerate(rows, start=1):
        kickoff = row["kickoff_utc"].astimezone(tz)
        group_or_round = row["round_name"] or round_label or "Плей-офф"

        score = ""
        if row["home_goals"] is not None and row["away_goals"] is not None:
            score = f" — {row['home_goals']}:{row['away_goals']}"

        lines = [
            f"{index}. {kickoff.strftime('%d.%m.%Y %H:%M')}",
            f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}{score}",
            str(group_or_round),
        ]

        if row["venue"]:
            lines.append(f"Стадион {row['venue']}")

        lines.append(f"Карточка: /match_{row['fixture_id']}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)
