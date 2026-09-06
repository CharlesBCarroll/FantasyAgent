"""Sleeper API client — free, no auth required.

Sleeper doesn't expose fantasy point projections publicly, so this module is
used for player metadata and momentum signals (trending adds/drops) rather
than point projections. Sleeper player ids don't line up with Yahoo/ESPN ids,
so lookups join on normalized player name.
"""

import requests

from fantasy_agent.utils import normalize_name

BASE_URL = "https://api.sleeper.app/v1"

_players_cache: dict | None = None


def get_all_players() -> dict:
    """Return Sleeper's full player directory, keyed by sleeper player_id.

    This payload is a few MB; cache it for the lifetime of the process
    since it only changes a handful of times per week.
    """
    global _players_cache
    if _players_cache is None:
        resp = requests.get(f"{BASE_URL}/players/nfl", timeout=30)
        resp.raise_for_status()
        _players_cache = resp.json()
    return _players_cache


def _name_index() -> dict[str, dict]:
    return {
        normalize_name(p["full_name"]): p
        for p in get_all_players().values()
        if p.get("full_name")
    }


def get_trending(direction: str = "add", lookback_hours: int = 24, limit: int = 50) -> dict[str, int]:
    """Return {normalized_name: add/drop_count} for trending players."""
    resp = requests.get(
        f"{BASE_URL}/players/nfl/trending/{direction}",
        params={"lookback_hours": lookback_hours, "limit": limit},
        timeout=15,
    )
    resp.raise_for_status()
    players = get_all_players()
    trending = {}
    for entry in resp.json():
        player = players.get(entry["player_id"])
        if player and player.get("full_name"):
            trending[normalize_name(player["full_name"])] = entry["count"]
    return trending


def lookup_by_name(name: str) -> dict | None:
    return _name_index().get(normalize_name(name))
