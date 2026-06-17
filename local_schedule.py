\
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


SCHEDULE_PATH = Path(__file__).with_name("schedule.json")


ROUND_TRANSLATIONS = {
    "Round of 32": "1/16 финала",
    "Round of 16": "1/8 финала",
    "Quarter-final": "1/4 финала",
    "Semi-final": "1/2 финала",
    "Match for third place": "Матч за 3-е место",
    "Final": "Финал",
}


def _parse_time(date_str: str, time_str: str) -> datetime:
    """
    Поддерживает формат OpenFootball:
    "13:00 UTC-6", "20:30 UTC-4", "15:00 UTC+2".
    Возвращает datetime в UTC.
    """
    m = re.fullmatch(r"(\d{2}:\d{2})\s+UTC([+-]\d{1,2})(?::?(\d{2}))?", time_str.strip())
    if not m:
        raise ValueError(f"Unsupported time format: {time_str}")

    hhmm = m.group(1)
    hours = int(m.group(2))
    minutes = int(m.group(3) or "0")

    # UTC-6 значит локальное время = UTC-06:00.
    offset = timezone(timedelta(hours=hours, minutes=minutes if hours >= 0 else -minutes))
    local_dt = datetime.fromisoformat(f"{date_str}T{hhmm}:00").replace(tzinfo=offset)
    return local_dt.astimezone(timezone.utc)


def _group_label(group: str | None) -> str | None:
    if not group:
        return None
    group = str(group)
    if group.startswith("Group "):
        return "Группа " + group.replace("Group ", "")
    return group


def _round_label(round_name: str | None) -> str | None:
    if not round_name:
        return None
    return ROUND_TRANSLATIONS.get(str(round_name), str(round_name))


def _score_part(match: dict[str, Any]):
    score = match.get("score") or {}
    ft = score.get("ft") if isinstance(score, dict) else None
    if isinstance(ft, list) and len(ft) == 2:
        return int(ft[0]), int(ft[1])
    return None, None


def load_matches() -> list[dict[str, Any]]:
    with SCHEDULE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    raw_matches = data.get("matches", [])
    result = []

    for idx, match in enumerate(raw_matches, start=1):
        home_goals, away_goals = _score_part(match)
        result.append(
            {
                "fixture_id": int(match.get("num") or idx),
                "kickoff_utc": _parse_time(match["date"], match["time"]),
                "home_team": str(match["team1"]),
                "away_team": str(match["team2"]),
                "group_name": _group_label(match.get("group")),
                "round_name": _round_label(match.get("round")),
                "venue": match.get("ground"),
                "status_short": "NS" if home_goals is None else "FT",
                "status_long": "Scheduled" if home_goals is None else "Full Time",
                "home_goals": home_goals,
                "away_goals": away_goals,
                "raw": json.dumps(match, ensure_ascii=False),
            }
        )

    return result
