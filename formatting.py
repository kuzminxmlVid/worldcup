\
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def day_bounds_utc(day, tz: ZoneInfo):
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def match_line(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    date_time = kickoff.strftime("%d.%m, %H:%M")

    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    score = ""
    if row["home_goals"] is not None and row["away_goals"] is not None:
        score = f"  {row['home_goals']}:{row['away_goals']}"

    venue = f"\n{row['venue']}" if row["venue"] else ""

    return (
        f"⚽️ {date_time}\n"
        f"{row['home_team']} — {row['away_team']}{score}\n"
        f"{group_or_round}"
        f"{venue}"
    )


def format_matches(title: str, rows, tz: ZoneInfo) -> str:
    if not rows:
        return f"{title}\n\nМатчей нет."

    blocks = [match_line(row, tz) for row in rows]
    return title + "\n\n" + "\n\n".join(blocks)


def format_reminder(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group_or_round = row["group_name"] or row["round_name"] or "Стадия не указана"

    return (
        "🔔 Через час матч ЧМ\n\n"
        f"⚽️ {kickoff.strftime('%d.%m, %H:%M')}\n"
        f"{row['home_team']} — {row['away_team']}\n"
        f"{group_or_round}"
    )


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
            lines.append(f"{kickoff} — {row['home_team']} — {row['away_team']}")
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
