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

    group = row["group_name"] or row["round_name"] or "Группа не указана"

    score = ""
    if row["home_goals"] is not None and row["away_goals"] is not None:
        score = f"  {row['home_goals']}:{row['away_goals']}"

    place_parts = [p for p in [row["venue"], row["city"]] if p]
    place = ""
    if place_parts:
        place = "\n" + ", ".join(place_parts)

    return (
        f"⚽️ {date_time}\n"
        f"{row['home_team']} — {row['away_team']}{score}\n"
        f"{group}"
        f"{place}"
    )


def format_matches(title: str, rows, tz: ZoneInfo) -> str:
    if not rows:
        return f"{title}\n\nМатчей нет."

    blocks = [match_line(row, tz) for row in rows]
    return title + "\n\n" + "\n\n".join(blocks)


def format_reminder(row, tz: ZoneInfo) -> str:
    kickoff = row["kickoff_utc"].astimezone(tz)
    group = row["group_name"] or row["round_name"] or "Группа не указана"

    return (
        "🔔 Через час матч ЧМ\n\n"
        f"⚽️ {kickoff.strftime('%d.%m, %H:%M')}\n"
        f"{row['home_team']} — {row['away_team']}\n"
        f"{group}"
    )
