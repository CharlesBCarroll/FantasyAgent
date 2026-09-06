"""Historical/context signals derived from nflverse data via nfl_data_py.

nfl_data_py has no forward-looking projections either — it's actual/historical
play-by-play-derived weekly stats and injury reports. We derive two signals
from it: a recent-performance trend (proxy for "current form") and an
opponent-defense-strength rank (proxy for matchup difficulty). Both feed
blend.py alongside each platform's own native projection (which already
reflects the league's real scoring settings). Since these signals are
computed from raw stats, they must use the same scoring format as the
league they're being used for, or they'll systematically mislead a
non-PPR/half-PPR league.
"""

import nfl_data_py as nfl
import pandas as pd

from fantasy_agent.utils import normalize_name

_weekly_cache: dict[int, pd.DataFrame] = {}
_injury_cache: dict[int, pd.DataFrame] = {}

SCORING_PRESETS = {
    "ppr": {"reception": 1.0},
    "half_ppr": {"reception": 0.5},
    "standard": {"reception": 0.0},
}

DEFAULT_COEFFICIENTS = {
    "pass_yd_per_point": 25,
    "pass_td": 4,
    "interception": -2,
    "rush_yd_per_point": 10,
    "rush_td": 6,
    "reception": 1.0,  # full PPR unless overridden
    "rec_yd_per_point": 10,
    "rec_td": 6,
    "fumble_lost": -2,
}


def resolve_scoring(scoring: str | dict | None) -> dict:
    """Turn a league's `scoring` config value into a full coefficient dict.

    Accepts a preset name ("ppr" / "half_ppr" / "standard"), a dict of
    coefficient overrides, or None (defaults to full PPR).
    """
    if scoring is None:
        overrides = {}
    elif isinstance(scoring, str):
        overrides = SCORING_PRESETS.get(scoring, {})
    else:
        overrides = scoring
    return {**DEFAULT_COEFFICIENTS, **overrides}


def fantasy_points(row, scoring: dict) -> float:
    return (
        row.get("passing_yards", 0) / scoring["pass_yd_per_point"]
        + row.get("passing_tds", 0) * scoring["pass_td"]
        + row.get("interceptions", 0) * scoring["interception"]
        + row.get("rushing_yards", 0) / scoring["rush_yd_per_point"]
        + row.get("rushing_tds", 0) * scoring["rush_td"]
        + row.get("receptions", 0) * scoring["reception"]
        + row.get("receiving_yards", 0) / scoring["rec_yd_per_point"]
        + row.get("receiving_tds", 0) * scoring["rec_td"]
        + row.get("fumbles_lost", 0) * scoring["fumble_lost"]
    )


def _weekly_data(season: int) -> pd.DataFrame:
    if season not in _weekly_cache:
        _weekly_cache[season] = nfl.import_weekly_data([season])
    return _weekly_cache[season]


def _injury_data(season: int) -> pd.DataFrame:
    if season not in _injury_cache:
        _injury_cache[season] = nfl.import_injuries([season])
    return _injury_cache[season]


def recent_trend(
    player_name: str, season: int, through_week: int, scoring: dict, lookback: int = 4
) -> float | None:
    """Average fantasy points (in `scoring`'s format) over the last `lookback` games."""
    df = _weekly_data(season)
    target = normalize_name(player_name)
    mask = (df["player_display_name"].apply(normalize_name) == target) & (df["week"] < through_week)
    games = df[mask].sort_values("week").tail(lookback)
    if games.empty:
        return None
    return float(games.apply(lambda row: fantasy_points(row, scoring), axis=1).mean())


def opponent_defense_rank(
    position: str, opponent_team: str, season: int, through_week: int, scoring: dict
) -> int | None:
    """Rank of how many fantasy points `opponent_team` allows to `position` (1 = toughest matchup)."""
    df = _weekly_data(season)
    df = df[(df["week"] < through_week) & (df["position"] == position)].copy()
    if df.empty:
        return None
    df["points"] = df.apply(lambda row: fantasy_points(row, scoring), axis=1)
    allowed = df.groupby("opponent_team")["points"].mean().sort_values()
    if opponent_team not in allowed.index:
        return None
    ranks = allowed.rank(method="min").astype(int)
    return int(ranks[opponent_team])


def actual_points(player_name: str, season: int, week: int, scoring: dict) -> float | None:
    """Fantasy points (in `scoring`'s format) a player actually scored in a given week."""
    df = _weekly_data(season)
    target = normalize_name(player_name)
    mask = (df["player_display_name"].apply(normalize_name) == target) & (df["week"] == week)
    rows = df[mask]
    if rows.empty:
        return None
    return float(fantasy_points(rows.iloc[-1], scoring))


def injury_status(player_name: str, season: int, week: int) -> str | None:
    df = _injury_data(season)
    target = normalize_name(player_name)
    mask = (df["full_name"].apply(normalize_name) == target) & (df["week"] == week)
    rows = df[mask]
    if rows.empty:
        return None
    return rows.iloc[-1].get("report_status")
