from collections import OrderedDict
from datetime import datetime, time, timedelta, timezone
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
    "Группа A": "🅰️",
    "Группа B": "🅱️",
    "Группа C": "🇨",
    "Группа D": "🇩",
    "Группа E": "🇪",
    "Группа F": "🇫",
    "Группа G": "🇬",
    "Группа H": "🇭",
    "Группа I": "🇮",
    "Группа J": "🇯",
    "Группа K": "🇰",
    "Группа L": "🇱",
}


def day_bounds_utc(day, tz: ZoneInfo):
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def team_with_flag(name: str) -> str:
    return f"{TEAM_FLAGS.get(name, '🏳️')} {name}"


def stage_with_icon(group_or_round: str) -> str:
    if not group_or_round:
        return "🏷️ Стадия не указана"
    return f"{GROUP_ICONS.get(group_or_round, '🏷️')} {group_or_round}"


def match_line(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    score = ""
    if row["home_goals"] is not None and row["away_goals"] is not None:
        score = f"  •  {row['home_goals']}:{row['away_goals']}"

    lines = [
        f"🕒 {kickoff.strftime('%H:%M')}",
        f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}{score}",
        stage_with_icon(group_or_round),
    ]

    if row["venue"]:
        lines.append(f"🏟️ {row['venue']}")

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
        parts.append(f"📅 {day.strftime('%d.%m.%Y')}")
        for row in day_rows:
            parts.append(match_line(row, tz))
    return "\n\n".join(parts)


def format_reminder(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    lines = [
        "🔔 Через час матч ЧМ",
        f"🕒 {kickoff.strftime('%d.%m, %H:%M')}",
        f"{team_with_flag(row['home_team'])} — {team_with_flag(row['away_team'])}",
        stage_with_icon(group_or_round),
    ]
    if row["venue"]:
        lines.append(f"🏟️ {row['venue']}")
    return "\n".join(lines)


def format_debug(count, first_row, last_row, next_rows, tz: ZoneInfo) -> str:
    lines = ["🧪 Debug", f"Матчей в базе: {count}"]

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
