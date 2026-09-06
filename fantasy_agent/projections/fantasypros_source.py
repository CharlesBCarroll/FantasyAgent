"""FantasyPros consensus projections — third blend source.

Verified against a real API key (2026-09-06): the free tier caps every
request at 10 players no matter what filter is used (position, limit,
page_size, per_page all tried — all capped at 10). So this only covers the
top ~10 projected players per position each week, not the full player pool.
Still a real, useful signal for actual starters and elite waiver adds; falls
back to None (no blend contribution) for everyone else, same as any other
source when data is unavailable — never blocks recommendations.

The `scoring` query param appears to have no effect on the response — every
player's stats block always includes points/points_ppr/points_half
together — so we fetch once per (season, week, position) and pick the right
field client-side based on the league's actual scoring format.
"""

import os

import requests

from fantasy_agent.utils import normalize_name

BASE_URL = "https://api.fantasypros.com/public/v2/json/nfl"

# Our internal position codes -> FantasyPros' position codes (only D/ST differs).
POSITION_PARAM = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "D/ST": "DST"}
STATS_KEY_BY_SCORING = {"ppr": "points_ppr", "half_ppr": "points_half", "standard": "points"}

_projections_cache: dict[tuple[int, int, str], dict[str, dict]] = {}


def _stats_key(scoring: str | dict | None) -> str:
    if isinstance(scoring, str):
        return STATS_KEY_BY_SCORING.get(scoring, "points_ppr")
    return "points_ppr"


def _fetch_position(season: int, week: int, position_param: str) -> dict[str, dict]:
    api_key = os.environ.get("FANTASYPROS_API_KEY")
    if not api_key:
        return {}

    cache_key = (season, week, position_param)
    if cache_key in _projections_cache:
        return _projections_cache[cache_key]

    try:
        resp = requests.get(
            f"{BASE_URL}/{season}/projections",
            params={"week": week, "position": position_param},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        resp.raise_for_status()
        players = resp.json().get("players", [])
        result = {normalize_name(p["name"]): p["stats"] for p in players if p.get("name") and p.get("stats")}
    except Exception:
        result = {}

    _projections_cache[cache_key] = result
    return result


def get_projection(
    player_name: str, position: str, season: int, week: int, scoring: str | dict | None = None
) -> float | None:
    """FantasyPros consensus projected points for this player/week, or None if unavailable.

    Only covers the top ~10 projected players at `position` this week (free
    tier limit) — a miss here just means "not currently a top-10 projection
    at this position," not an error.
    """
    position_param = POSITION_PARAM.get(position)
    if position_param is None:
        return None
    stats = _fetch_position(season, week, position_param).get(normalize_name(player_name))
    if stats is None:
        return None
    return stats.get(_stats_key(scoring))
