"""Fixtures tool.

Adapter over football-data.org's World Cup feed with a bundled mock
fallback, so the whole demo runs end to end without a second API key.
The agent never knows which source it hit — the schema is identical.
"""

import json
from datetime import date, datetime, timedelta

import httpx

from ..config import settings

API_BASE = "https://api.football-data.org/v4/competitions/WC/matches"


def _load_mock() -> list[dict]:
    with open(settings.data_dir / "mock" / "fixtures.json") as f:
        return json.load(f)


def _normalize_api(match: dict) -> dict:
    score = match.get("score", {}).get("fullTime", {})
    return {
        "date": match.get("utcDate", "")[:10],
        "kickoff_utc": match.get("utcDate", ""),
        "stage": match.get("stage", ""),
        "group": (match.get("group") or "").replace("GROUP_", "Group "),
        "home_team": match.get("homeTeam", {}).get("name", ""),
        "away_team": match.get("awayTeam", {}).get("name", ""),
        "status": match.get("status", ""),
        "score": {
            "home": score.get("home"),
            "away": score.get("away"),
        },
        "venue": match.get("venue", ""),
    }


async def get_fixtures(
    date_from: str | None = None,
    date_to: str | None = None,
    team: str | None = None,
) -> dict:
    """Return World Cup fixtures/results in a window (default: today ± 3 days)."""
    today = date.today()
    start = date_from or str(today - timedelta(days=1))
    end = date_to or str(today + timedelta(days=3))

    matches: list[dict]
    source = "mock"

    if settings.football_data_api_key:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    API_BASE,
                    params={"dateFrom": start, "dateTo": end},
                    headers={"X-Auth-Token": settings.football_data_api_key},
                )
                resp.raise_for_status()
                matches = [_normalize_api(m) for m in resp.json().get("matches", [])]
                source = "football-data.org"
        except (httpx.HTTPError, KeyError, ValueError):
            matches = _load_mock()
    else:
        matches = _load_mock()

    if source == "mock":
        matches = [m for m in matches if start <= m["date"] <= end]

    if team:
        t = team.strip().lower()
        matches = [
            m
            for m in matches
            if t in m["home_team"].lower() or t in m["away_team"].lower()
        ]

    return {
        "source": source,
        "window": {"from": start, "to": end},
        "match_count": len(matches),
        "matches": matches[:25],
        "retrieved_at": datetime.utcnow().isoformat() + "Z",
    }
