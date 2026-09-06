"""FantasyPros consensus projections — third blend source.

Blocked on Charles's API key request (https://secure.fantasypros.com/api-keys/request/)
being approved. Ships inert: without FANTASYPROS_API_KEY set, get_projection()
always returns None, so this plugs into project_player's `sources` dict with
zero behavior change until a key is granted.

Endpoint shape is inferred from FantasyPros v2 docs
(https://api.fantasypros.com/public/v2/docs) rather than verified against a
live key — spot-check the URL path, query params, and response field names
once a real key exists, same caveat already applied to yfpy's Yahoo surface.
"""

import os

import requests

from fantasy_agent.utils import normalize_name

BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"

SCORING_PARAM = {"ppr": "PPR", "half_ppr": "HALF", "standard": "STD"}
STATS_KEY_BY_SCORING_PARAM = {"PPR": "points_ppr", "HALF": "points_half", "STD": "points"}

_projections_cache: dict[tuple[int, int, str], dict[str, float]] = {}


def _scoring_param(scoring: str | dict | None) -> str:
    if isinstance(scoring, str):
        return SCORING_PARAM.get(scoring, "PPR")
    return "PPR"


def _fetch_projections(season: int, week: int, scoring_param: str) -> dict[str, float]:
    api_key = os.environ.get("FANTASYPROS_API_KEY")
    if not api_key:
        return {}

    cache_key = (season, week, scoring_param)
    if cache_key in _projections_cache:
        return _projections_cache[cache_key]

    try:
        resp = requests.get(
            f"{BASE_URL}/{season}/projections",
            params={"week": week, "scoring": scoring_param},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        players = resp.json().get("players", [])
        stats_key = STATS_KEY_BY_SCORING_PARAM[scoring_param]
        result = {
            normalize_name(p["name"]): p["stats"][stats_key]
            for p in players
            if p.get("name") and stats_key in p.get("stats", {})
        }
    except Exception:
        result = {}

    _projections_cache[cache_key] = result
    return result


def get_projection(player_name: str, season: int, week: int, scoring: str | dict | None = None) -> float | None:
    """FantasyPros consensus projected points for this player/week, or None if unavailable."""
    projections = _fetch_projections(season, week, _scoring_param(scoring))
    return projections.get(normalize_name(player_name))
