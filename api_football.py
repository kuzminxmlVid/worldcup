\
import json
from datetime import datetime, timezone
from typing import Any

import aiohttp


FIXTURES_PATH = "/fixtures"
STANDINGS_PATH = "/standings"

WORLD_CUP_LEAGUE_ID = 1
WORLD_CUP_SEASON = 2026


class ApiFootballClient:
    def __init__(self, api_key: str, host: str):
        self.base_url = f"https://{host}"
        self.headers = {
            "x-apisports-key": api_key,
        }

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(self.base_url + path, params=params, timeout=30) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"API-Football error {resp.status}: {text}")
                return json.loads(text)

    async def get_fixtures(self) -> list[dict[str, Any]]:
        data = await self._get(
            FIXTURES_PATH,
            {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON},
        )
        return data.get("response", [])

    async def get_group_map(self) -> dict[int, str]:
        """
        Возвращает {team_id: 'Group A'}.

        API-Football обычно отдаёт standings как список групп:
        response[0].league.standings = [
            [team rows for Group A],
            [team rows for Group B],
            ...
        ]
        """
        data = await self._get(
            STANDINGS_PATH,
            {"league": WORLD_CUP_LEAGUE_ID, "season": WORLD_CUP_SEASON},
        )

        group_map: dict[int, str] = {}

        for item in data.get("response", []):
            standings = item.get("league", {}).get("standings", [])
            for group_rows in standings:
                for row in group_rows:
                    team = row.get("team", {})
                    team_id = team.get("id")
                    group = row.get("group")
                    if team_id and group:
                        group_map[int(team_id)] = group

        return group_map


def normalize_fixture(item: dict[str, Any], group_map: dict[int, str]) -> dict[str, Any]:
    fixture = item["fixture"]
    teams = item["teams"]
    league = item.get("league", {})
    goals = item.get("goals") or {}

    home = teams["home"]
    away = teams["away"]

    home_id = home.get("id")
    away_id = away.get("id")

    group_name = None
    if home_id in group_map:
        group_name = group_map[home_id]
    elif away_id in group_map:
        group_name = group_map[away_id]

    kickoff = datetime.fromisoformat(
        fixture["date"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)

    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}

    return {
        "fixture_id": int(fixture["id"]),
        "kickoff_utc": kickoff,
        "home_team": home["name"],
        "away_team": away["name"],
        "group_name": group_name,
        "round_name": league.get("round"),
        "venue": venue.get("name"),
        "city": venue.get("city"),
        "status_short": status.get("short"),
        "status_long": status.get("long"),
        "home_goals": goals.get("home"),
        "away_goals": goals.get("away"),
        "raw": json.dumps(item),
    }
