"""Dixon-Coles match simulator.

A compact analytic implementation: per-team attack/defence multipliers
drive Poisson goal expectations, with the Dixon-Coles tau correction for
the known dependence between low-scoring outcomes (0-0, 1-0, 0-1, 1-1).
Outcome probabilities are computed exactly from the joint score matrix
rather than by Monte Carlo, so results are deterministic and fast.

Ratings are illustrative tiers (loosely Elo-derived, June 2026) and are
deliberately swappable — the production version of this model lives in my
World Cup forecasting project, which fits attack/defence strengths by
maximum likelihood on historical internationals.
"""

import json
import math
from functools import lru_cache

from ..config import settings

BASE_GOALS = 1.32  # avg goals per team per match at recent World Cups
RHO = -0.08        # Dixon-Coles low-score dependence parameter
HOSTS = {"United States", "Mexico", "Canada"}
HOST_BOOST = 1.12  # mild host-nation attacking boost
MAX_GOALS = 10


@lru_cache(maxsize=1)
def _ratings() -> dict:
    with open(settings.data_dir / "ratings.json") as f:
        return json.load(f)


def _resolve(team: str) -> tuple[str, dict] | None:
    ratings = _ratings()
    if team in ratings:
        return team, ratings[team]
    lowered = team.strip().lower()
    for name, r in ratings.items():
        if lowered == name.lower() or lowered in [
            a.lower() for a in r.get("aliases", [])
        ]:
            return name, r
    return None


def _tau(x: int, y: int, lx: float, ly: float) -> float:
    """Dixon-Coles correction for the four low-score cells."""
    if x == 0 and y == 0:
        return 1 - lx * ly * RHO
    if x == 0 and y == 1:
        return 1 + lx * RHO
    if x == 1 and y == 0:
        return 1 + ly * RHO
    if x == 1 and y == 1:
        return 1 - RHO
    return 1.0


def _poisson(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def simulate_match(home_team: str, away_team: str) -> dict:
    home = _resolve(home_team)
    away = _resolve(away_team)
    if not home or not away:
        missing = home_team if not home else away_team
        return {
            "error": f"No ratings found for '{missing}'. "
            "Check the team name against the 48 qualified nations."
        }

    (h_name, h), (a_name, a) = home, away

    lam_h = BASE_GOALS * h["attack"] * a["defence"]
    lam_a = BASE_GOALS * a["attack"] * h["defence"]
    if h_name in HOSTS:
        lam_h *= HOST_BOOST
    if a_name in HOSTS:
        lam_a *= HOST_BOOST

    # Joint score matrix with DC correction, renormalised.
    matrix = {}
    total = 0.0
    for x in range(MAX_GOALS + 1):
        for y in range(MAX_GOALS + 1):
            p = _poisson(x, lam_h) * _poisson(y, lam_a) * _tau(x, y, lam_h, lam_a)
            matrix[(x, y)] = p
            total += p
    for k in matrix:
        matrix[k] /= total

    p_home = sum(p for (x, y), p in matrix.items() if x > y)
    p_away = sum(p for (x, y), p in matrix.items() if x < y)
    p_draw = 1 - p_home - p_away
    p_over_2_5 = sum(p for (x, y), p in matrix.items() if x + y >= 3)
    p_btts = sum(p for (x, y), p in matrix.items() if x >= 1 and y >= 1)

    top_scores = sorted(matrix.items(), key=lambda kv: -kv[1])[:5]

    return {
        "model": "dixon_coles_v1",
        "home_team": h_name,
        "away_team": a_name,
        "expected_goals": {h_name: round(lam_h, 2), a_name: round(lam_a, 2)},
        "probabilities": {
            f"{h_name}_win": round(p_home, 4),
            "draw": round(p_draw, 4),
            f"{a_name}_win": round(p_away, 4),
        },
        "over_2_5_goals": round(p_over_2_5, 4),
        "both_teams_score": round(p_btts, 4),
        "most_likely_scorelines": [
            {"score": f"{x}-{y}", "probability": round(p, 4)}
            for (x, y), p in top_scores
        ],
        "notes": "Host nations receive a small attacking boost. "
        "Ratings are tier-based and illustrative.",
    }
