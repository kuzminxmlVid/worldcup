import asyncio
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher


API_BASE_URL = "https://v3.football.api-sports.io"
DEFAULT_LEAGUE_ID = int(os.getenv("API_FOOTBALL_LEAGUE_ID", "1"))
DEFAULT_SEASON = int(os.getenv("API_FOOTBALL_SEASON", "2026"))


class ApiFootballError(Exception):
    pass


API_TEAM_ALIASES = {
    "usa": "usa",
    "united states": "usa",
    "south korea": "korea republic",
    "korea republic": "korea republic",
    "dr congo": "congo dr",
    "d r congo": "congo dr",
    "congo dr": "congo dr",
    "czech republic": "czech republic",
    "ivory coast": "cote divoire",
    "cote d ivoire": "cote divoire",
    "côte d’ivoire": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "bosnia and herzegovina": "bosnia herzegovina",
    "bosnia & herzegovina": "bosnia herzegovina",
}


def _api_key() -> str:
    key = os.getenv("API_FOOTBALL_KEY") or os.getenv("APISPORTS_KEY")
    if not key:
        raise ApiFootballError(
            "API_FOOTBALL_KEY is not set. Add it in Railway variables."
        )
    return key


def _normalize_team(name: str) -> str:
    text = str(name).lower().replace("&", " and ")
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    text = " ".join(text.split())
    return API_TEAM_ALIASES.get(text, text)


def _similar(a: str, b: str) -> float:
    a_norm = _normalize_team(a)
    b_norm = _normalize_team(b)

    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92

    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _parse_api_date(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _request_fixtures(params: dict) -> list[dict]:
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE_URL}/fixtures?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "x-apisports-key": _api_key(),
            "User-Agent": "worldcup-telegram-bot/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            import json

            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ApiFootballError(f"API-Football HTTP error: {e.code}") from e
    except urllib.error.URLError as e:
        raise ApiFootballError(f"API-Football network error: {e}") from e
    except TimeoutError as e:
        raise ApiFootballError("API-Football timeout") from e

    errors = payload.get("errors")
    if errors:
        raise ApiFootballError(f"API-Football error: {errors}")

    return payload.get("response", []) or []


def _fixture_result_from_item(local_row, item: dict) -> dict:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}
    status = fixture.get("status") or {}

    api_home = (teams.get("home") or {}).get("name") or ""
    api_away = (teams.get("away") or {}).get("name") or ""

    local_home = local_row["home_team"]
    local_away = local_row["away_team"]

    same_order = (
        _similar(local_home, api_home) >= 0.72
        and _similar(local_away, api_away) >= 0.72
    )
    reversed_order = (
        _similar(local_home, api_away) >= 0.72
        and _similar(local_away, api_home) >= 0.72
    )

    home_goals = goals.get("home")
    away_goals = goals.get("away")

    if reversed_order:
        home_goals, away_goals = away_goals, home_goals

    return {
        "api_fixture_id": fixture.get("id"),
        "status_short": status.get("short"),
        "status_long": status.get("long"),
        "elapsed": status.get("elapsed"),
        "home_goals": home_goals,
        "away_goals": away_goals,
        "api_home_team": api_home,
        "api_away_team": api_away,
        "api_date": fixture.get("date"),
    }


def _best_fixture_match(local_row, items: list[dict]) -> dict | None:
    local_home = local_row["home_team"]
    local_away = local_row["away_team"]
    local_kickoff = local_row["kickoff_utc"]
    if local_kickoff.tzinfo is None:
        local_kickoff = local_kickoff.replace(tzinfo=timezone.utc)

    best_item = None
    best_score = -1.0

    for item in items:
        fixture = item.get("fixture") or {}
        teams = item.get("teams") or {}
        api_home = (teams.get("home") or {}).get("name") or ""
        api_away = (teams.get("away") or {}).get("name") or ""

        same_order = (
            _similar(local_home, api_home) + _similar(local_away, api_away)
        ) / 2
        reversed_order = (
            _similar(local_home, api_away) + _similar(local_away, api_home)
        ) / 2
        team_score = max(same_order, reversed_order)

        api_dt = _parse_api_date(fixture.get("date"))
        time_score = 0.0
        if api_dt:
            diff_hours = abs((api_dt.astimezone(timezone.utc) - local_kickoff.astimezone(timezone.utc)).total_seconds()) / 3600
            if diff_hours <= 2:
                time_score = 0.30
            elif diff_hours <= 24:
                time_score = 0.12

        score = team_score + time_score

        if score > best_score:
            best_score = score
            best_item = item

    if not best_item or best_score < 0.92:
        return None

    return _fixture_result_from_item(local_row, best_item)


def _fetch_score_sync(local_row) -> dict:
    cached_api_id = local_row.get("api_fixture_id") if hasattr(local_row, "get") else local_row["api_fixture_id"]

    if cached_api_id:
        items = _request_fixtures({"id": cached_api_id})
        if items:
            return _fixture_result_from_item(local_row, items[0])

    kickoff = local_row["kickoff_utc"]
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)

    base_date = kickoff.astimezone(timezone.utc).date()
    dates = [
        base_date.isoformat(),
        (base_date - timedelta(days=1)).isoformat(),
        (base_date + timedelta(days=1)).isoformat(),
    ]

    checked_items = []
    for date in dates:
        items = _request_fixtures(
            {
                "league": DEFAULT_LEAGUE_ID,
                "season": DEFAULT_SEASON,
                "date": date,
            }
        )
        checked_items.extend(items)

        found = _best_fixture_match(local_row, items)
        if found:
            return found

    found = _best_fixture_match(local_row, checked_items)
    if found:
        return found

    raise ApiFootballError(
        "Не нашёл матч в API-Football. Возможно, в API другие названия команд или турнир ещё не опубликован."
    )


async def fetch_score_for_match(local_row) -> dict:
    return await asyncio.to_thread(_fetch_score_sync, local_row)
