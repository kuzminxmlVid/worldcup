import asyncio
import re
import urllib.parse
import urllib.request
import urllib.error
from datetime import timedelta, timezone
from difflib import SequenceMatcher


ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"


class ApiFootballError(Exception):
    pass


TEAM_ALIASES = {
    "usa": "united states",
    "united states": "united states",
    "united states of america": "united states",
    "south korea": "korea republic",
    "korea republic": "korea republic",
    "republic of korea": "korea republic",
    "dr congo": "congo dr",
    "d r congo": "congo dr",
    "congo dr": "congo dr",
    "democratic republic of congo": "congo dr",
    "czech republic": "czech republic",
    "czechia": "czech republic",
    "ivory coast": "cote divoire",
    "cote divoire": "cote divoire",
    "cote d ivoire": "cote divoire",
    "côte d’ivoire": "cote divoire",
    "côte d'ivoire": "cote divoire",
    "bosnia & herzegovina": "bosnia herzegovina",
    "bosnia and herzegovina": "bosnia herzegovina",
}


def _row_get(row, key: str, default=None):
    try:
        value = row.get(key, default)
        return default if value is None else value
    except AttributeError:
        try:
            value = row[key]
            return default if value is None else value
        except Exception:
            return default


def _normalize_team(name: str) -> str:
    text = str(name).lower().replace("&", " and ")
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    text = " ".join(text.split())
    return TEAM_ALIASES.get(text, text)


def _similar(a: str, b: str) -> float:
    a_norm = _normalize_team(a)
    b_norm = _normalize_team(b)

    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92

    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _request_scoreboard(params: dict) -> list[dict]:
    query = urllib.parse.urlencode(params)
    url = ESPN_BASE_URL if not query else f"{ESPN_BASE_URL}?{query}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "worldcup-telegram-bot/1.0"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ApiFootballError(f"ESPN HTTP error: {e.code}") from e
    except urllib.error.URLError as e:
        raise ApiFootballError(f"ESPN network error: {e}") from e
    except TimeoutError as e:
        raise ApiFootballError("ESPN timeout") from e

    return payload.get("events", []) or []


def _parse_score(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_espn_datetime(value: str):
    if not value:
        return None

    try:
        return __import__("datetime").datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _teams_from_event(event: dict):
    competitions = event.get("competitions") or []
    if not competitions:
        return None

    comp = competitions[0]
    competitors = comp.get("competitors") or []

    home = None
    away = None

    for item in competitors:
        home_away = item.get("homeAway")
        team = item.get("team") or {}
        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name") or ""
        score = _parse_score(item.get("score"))

        if home_away == "home":
            home = {"name": name, "score": score}
        elif home_away == "away":
            away = {"name": name, "score": score}

    if not home or not away:
        return None

    return home, away, comp


def _status_from_comp(comp: dict):
    status = comp.get("status") or {}
    status_type = status.get("type") or {}

    state = status_type.get("state")
    completed = bool(status_type.get("completed"))
    name = status_type.get("name") or ""
    description = status_type.get("description") or ""
    detail = status_type.get("detail") or ""
    short_detail = status_type.get("shortDetail") or ""

    if completed:
        return "FT", description or "Full Time"

    if state == "in":
        return "LIVE", detail or short_detail or description or name or "Live"

    if state == "pre":
        return "NS", description or "Scheduled"

    return name or "UNK", description or detail or short_detail or "Unknown"


def _result_from_event(local_row, event: dict) -> dict | None:
    teams = _teams_from_event(event)
    if not teams:
        return None

    api_home, api_away, comp = teams

    local_home = _row_get(local_row, "home_team", "")
    local_away = _row_get(local_row, "away_team", "")

    same_order = (
        _similar(local_home, api_home["name"]) >= 0.70
        and _similar(local_away, api_away["name"]) >= 0.70
    )
    reversed_order = (
        _similar(local_home, api_away["name"]) >= 0.70
        and _similar(local_away, api_home["name"]) >= 0.70
    )

    if not same_order and not reversed_order:
        return None

    home_goals = api_home["score"]
    away_goals = api_away["score"]

    if reversed_order:
        home_goals, away_goals = away_goals, home_goals

    status_short, status_long = _status_from_comp(comp)

    return {
        "api_fixture_id": _parse_score(event.get("id")),
        "status_short": status_short,
        "status_long": status_long,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "api_home_team": api_home["name"],
        "api_away_team": api_away["name"],
        "api_date": event.get("date"),
    }


def _best_event_match(local_row, events: list[dict]) -> dict | None:
    local_home = _row_get(local_row, "home_team", "")
    local_away = _row_get(local_row, "away_team", "")

    local_kickoff = _row_get(local_row, "kickoff_utc")
    if local_kickoff and local_kickoff.tzinfo is None:
        local_kickoff = local_kickoff.replace(tzinfo=timezone.utc)

    best_event = None
    best_score = -1.0

    for event in events:
        teams = _teams_from_event(event)
        if not teams:
            continue

        api_home, api_away, _ = teams

        same_order = (
            _similar(local_home, api_home["name"])
            + _similar(local_away, api_away["name"])
        ) / 2

        reversed_order = (
            _similar(local_home, api_away["name"])
            + _similar(local_away, api_home["name"])
        ) / 2

        team_score = max(same_order, reversed_order)

        time_score = 0.0
        api_dt = _parse_espn_datetime(event.get("date"))
        if local_kickoff and api_dt:
            diff_hours = abs(
                (
                    api_dt.astimezone(timezone.utc)
                    - local_kickoff.astimezone(timezone.utc)
                ).total_seconds()
            ) / 3600

            if diff_hours <= 3:
                time_score = 0.35
            elif diff_hours <= 24:
                time_score = 0.12

        score = team_score + time_score

        if score > best_score:
            best_score = score
            best_event = event

    if not best_event or best_score < 0.90:
        return None

    return _result_from_event(local_row, best_event)


def _fetch_score_sync(local_row) -> dict:
    cached_espn_event_id = _row_get(local_row, "api_fixture_id")
    if cached_espn_event_id:
        events = _request_scoreboard({"event": cached_espn_event_id})
        found = _best_event_match(local_row, events)
        if found:
            return found

    kickoff = _row_get(local_row, "kickoff_utc")
    if kickoff is None:
        events = _request_scoreboard({})
        found = _best_event_match(local_row, events)
        if found:
            return found

        raise ApiFootballError("ESPN не нашёл этот матч.")

    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)

    base_date = kickoff.astimezone(timezone.utc).date()
    dates = [
        base_date,
        base_date - timedelta(days=1),
        base_date + timedelta(days=1),
    ]

    checked_events = []
    for day in dates:
        events = _request_scoreboard({"dates": day.strftime("%Y%m%d")})
        checked_events.extend(events)

        found = _best_event_match(local_row, events)
        if found:
            return found

    found = _best_event_match(local_row, checked_events)
    if found:
        return found

    raise ApiFootballError(
        "ESPN не нашёл этот матч. Возможно, у ESPN другие названия команд или матч ещё не опубликован."
    )


async def fetch_score_for_match(local_row) -> dict:
    return await asyncio.to_thread(_fetch_score_sync, local_row)
