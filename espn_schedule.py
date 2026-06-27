import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone


ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
DEFAULT_START_DATE = os.getenv("WORLD_CUP_START_DATE", "2026-06-11")
DEFAULT_END_DATE = os.getenv("WORLD_CUP_END_DATE", "2026-07-19")


class EspnScheduleError(Exception):
    pass


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


TEAM_NAME_MAP = {
    "United States": "USA",
    "United States of America": "USA",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "Congo DR": "DR Congo",
    "Congo Democratic Republic": "DR Congo",
    "Democratic Republic of Congo": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Cote dIvoire": "Ivory Coast",
    "Côte d’ivoire": "Ivory Coast",
    "Bosnia-Herzegovina": "Bosnia & Herzegovina",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Czechia": "Czech Republic",
}


ROUND_NAME_MAP = {
    "group stage": "Групповой этап",
    "round of 32": "1/16 финала",
    "round of 16": "1/8 финала",
    "quarterfinals": "1/4 финала",
    "quarter-finals": "1/4 финала",
    "semifinals": "1/2 финала",
    "semi-finals": "1/2 финала",
    "third-place match": "Матч за 3-е место",
    "final": "Финал",
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _request_scoreboard(day: date) -> dict:
    params = {
        "dates": day.strftime("%Y%m%d"),
        "limit": 100,
    }
    url = f"{ESPN_SCOREBOARD_URL}?{urllib.parse.urlencode(params)}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "worldcup-telegram-bot/1.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise EspnScheduleError(f"ESPN HTTP error {e.code} for {day}") from e
    except urllib.error.URLError as e:
        raise EspnScheduleError(f"ESPN network error for {day}: {e}") from e
    except TimeoutError as e:
        raise EspnScheduleError(f"ESPN timeout for {day}") from e


def _normalize_team_name(name: str) -> str:
    name = (name or "").strip()
    return TEAM_NAME_MAP.get(name, name)


def _parse_score(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_kickoff(value: str) -> datetime:
    if not value:
        raise EspnScheduleError("ESPN event has no date")

    kickoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return kickoff.astimezone(timezone.utc)


def _status_from_competition(comp: dict) -> tuple[str | None, str | None]:
    comp = _as_dict(comp)
    status = _as_dict(comp.get("status"))
    status_type = _as_dict(status.get("type"))

    state = status_type.get("state")
    completed = bool(status_type.get("completed"))
    name = status_type.get("name")
    description = status_type.get("description")
    detail = status_type.get("detail") or status_type.get("shortDetail")

    if completed:
        return "FT", description or "Full Time"
    if state == "in":
        return "LIVE", detail or description or name or "Live"
    if state == "pre":
        return "NS", description or "Scheduled"

    return name or "UNK", description or detail or name or "Unknown"

def _round_name(event: dict, comp: dict) -> str | None:
    event = _as_dict(event)
    comp = _as_dict(comp)
    candidates = []

    season = _as_dict(event.get("season"))
    season_type = _as_dict(season.get("type"))
    if season_type.get("name"):
        candidates.append(str(season_type["name"]))

    # ESPN sometimes stores season.type as an integer. In that case there is no
    # readable round name here, so we simply skip it and continue with notes.
    if isinstance(season.get("type"), str):
        candidates.append(season["type"])

    for note in _as_list(comp.get("notes")):
        if isinstance(note, dict):
            headline = note.get("headline") or note.get("text")
            if headline:
                candidates.append(str(headline))
        elif note:
            candidates.append(str(note))

    # Another ESPN field that can contain "Round of 16", "Quarterfinal", etc.
    for key in ("name", "shortName"):
        if event.get(key):
            candidates.append(str(event[key]))

    for candidate in candidates:
        lowered = candidate.lower()
        for key, value in ROUND_NAME_MAP.items():
            if key in lowered:
                return value

    return candidates[0] if candidates else None

def _group_name(event: dict, comp: dict, round_name: str | None) -> str | None:
    event = _as_dict(event)
    comp = _as_dict(comp)

    if round_name and "групп" not in str(round_name).lower():
        return None

    candidates = []

    group = _as_dict(event.get("group"))
    for key in ("name", "shortName", "abbreviation"):
        if group.get(key):
            candidates.append(str(group[key]))

    for note in _as_list(comp.get("notes")):
        if isinstance(note, dict):
            text = note.get("headline") or note.get("text")
        else:
            text = note
        if text:
            candidates.append(str(text))

    for candidate in candidates:
        match = re.search(r"Group\s+([A-L])", candidate, re.IGNORECASE)
        if match:
            return f"Группа {match.group(1).upper()}"

    return None

def _venue(comp: dict) -> str | None:
    comp = _as_dict(comp)
    venue = _as_dict(comp.get("venue"))
    full_name = venue.get("fullName") or venue.get("name")
    if full_name:
        return str(full_name)

    address = _as_dict(venue.get("address"))
    city = address.get("city")
    if city:
        return str(city)

    return None

def _competitors(comp: dict) -> tuple[dict, dict] | None:
    comp = _as_dict(comp)
    home = None
    away = None

    for item in _as_list(comp.get("competitors")):
        item = _as_dict(item)
        team = _as_dict(item.get("team"))
        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name")
        score = _parse_score(item.get("score"))
        value = {
            "name": _normalize_team_name(str(name or "")),
            "score": score,
        }

        if item.get("homeAway") == "home":
            home = value
        elif item.get("homeAway") == "away":
            away = value

    if not home or not away or not home["name"] or not away["name"]:
        return None

    return home, away

def _event_to_match(event: dict) -> dict | None:
    event = _as_dict(event)
    competitions = _as_list(event.get("competitions"))
    if not competitions:
        return None

    comp = _as_dict(competitions[0])
    competitors = _competitors(comp)
    if not competitors:
        return None

    home, away = competitors
    status_short, status_long = _status_from_competition(comp)

    if status_short in ("NS", "TBD", "STATUS_SCHEDULED"):
        home_goals = None
        away_goals = None
    else:
        home_goals = home["score"]
        away_goals = away["score"]

    raw_id = event.get("id")
    try:
        fixture_id = int(raw_id)
    except (TypeError, ValueError):
        fixture_id = abs(hash((event.get("date"), home["name"], away["name"]))) % 10_000_000_000

    kickoff = _parse_kickoff(event.get("date"))
    round_name = _round_name(event, comp)

    return {
        "fixture_id": fixture_id,
        "kickoff_utc": kickoff,
        "home_team": home["name"],
        "away_team": away["name"],
        "group_name": _group_name(event, comp, round_name),
        "round_name": round_name,
        "venue": _venue(comp),
        "status_short": status_short,
        "status_long": status_long,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "raw": json.dumps({"source": "espn_scoreboard", "event": event}, ensure_ascii=False),
    }

def _fetch_world_cup_matches_sync(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
) -> list[dict]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    matches: dict[int, dict] = {}

    for day in _date_range(start, end):
        payload = _request_scoreboard(day)
        for event in payload.get("events", []) or []:
            match = _event_to_match(event)
            if match:
                matches[int(match["fixture_id"])] = match

    return sorted(matches.values(), key=lambda item: item["kickoff_utc"])


async def fetch_world_cup_matches() -> list[dict]:
    return await asyncio.to_thread(_fetch_world_cup_matches_sync)
