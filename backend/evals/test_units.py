"""Deterministic unit tests (no API key needed). Run: pytest evals/test_units.py"""

import asyncio
import json
from pathlib import Path

from app.rag.store import chunk_markdown
from app.tools.fixtures import get_fixtures
from app.tools.simulator import simulate_match

ROOT = Path(__file__).resolve().parents[1]


def test_probabilities_sum_to_one():
    r = simulate_match("Spain", "Haiti")
    assert abs(sum(r["probabilities"].values()) - 1) < 1e-3


def test_favorite_beats_minnow():
    r = simulate_match("Spain", "Haiti")
    assert r["probabilities"]["Spain_win"] > 0.7


def test_alias_resolution():
    r = simulate_match("USA", "Turkey")
    assert r["home_team"] == "United States"
    assert r["away_team"] == "Türkiye"


def test_unknown_team_returns_error():
    assert "error" in simulate_match("Spain", "Narnia")


def test_symmetry_without_host_boost():
    a = simulate_match("Japan", "Senegal")
    b = simulate_match("Senegal", "Japan")
    assert abs(a["probabilities"]["Japan_win"] - b["probabilities"]["Japan_win"]) < 0.01


def test_mock_fixtures_filter_by_team_and_window():
    fx = asyncio.run(
        get_fixtures(date_from="2026-06-11", date_to="2026-06-13", team="United States")
    )
    assert fx["source"] == "mock"
    assert fx["match_count"] == 1
    assert fx["matches"][0]["away_team"] == "Paraguay"


def test_chunker_splits_groups_doc():
    text = (ROOT / "data" / "knowledge" / "groups_2026.md").read_text()
    chunks = chunk_markdown(text, "groups_2026.md")
    assert len(chunks) >= 12
    assert any("Group D" in c["heading"] for c in chunks)


def test_all_48_teams_rated():
    ratings = json.loads((ROOT / "data" / "ratings.json").read_text())
    assert len(ratings) == 48
