"""Historical/context signals derived from nflverse data via nfl_data_py.

nfl_data_py has no forward-looking projections either — it's actual/historical
play-by-play-derived weekly stats and injury reports. We derive two signals
from it: a recent-performance trend (proxy for "current form") and an
opponent-defense-strength rank (proxy for matchup difficulty). Both feed
blend.py alongside each platform's own native projection.
"""

import nfl_data_py as nfl
import pandas as pd

from fantasy_agent.utils import normalize_name

_weekly_cache: dict[int, pd.DataFrame] = {}
_injury_cache: dict[int, pd.DataFrame] = {}


def _weekly_data(season: int) -> pd.DataFrame:
    if season not in _weekly_cache:
        _weekly_cache[season] = nfl.import_weekly_data([season])
    return _weekly_cache[season]


def _injury_data(season: int) -> pd.DataFrame:
    if season not in _injury_cache:
        _injury_cache[season] = nfl.import_injuries([season])
    return _injury_cache[season]


def ppr_points(row) -> float:
    return (
        row.get("passing_yards", 0) / 25
        + row.get("passing_tds", 0) * 4
        - row.get("interceptions", 0) * 2
        + row.get("rushing_yards", 0) / 10
        + row.get("rushing_tds", 0) * 6
        + row.get("receptions", 0) * 1
        + row.get("receiving_yards", 0) / 10
        + row.get("receiving_tds", 0) * 6
        - row.get("fumbles_lost", 0) * 2
    )


def recent_trend(player_name: str, season: int, through_week: int, lookback: int = 4) -> float | None:
    """Average PPR points over the last `lookback` games before through_week."""
    df = _weekly_data(season)
    target = normalize_name(player_name)
    mask = (df["player_display_name"].apply(normalize_name) == target) & (df["week"] < through_week)
    games = df[mask].sort_values("week").tail(lookback)
    if games.empty:
        return None
    return float(games.apply(ppr_points, axis=1).mean())


def opponent_defense_rank(position: str, opponent_team: str, season: int, through_week: int) -> int | None:
    """Rank of how many PPR points `opponent_team` allows to `position` (1 = toughest matchup)."""
    df = _weekly_data(season)
    df = df[(df["week"] < through_week) & (df["position"] == position)].copy()
    if df.empty:
        return None
    df["points"] = df.apply(ppr_points, axis=1)
    allowed = df.groupby("opponent_team")["points"].mean().sort_values()
    if opponent_team not in allowed.index:
        return None
    ranks = allowed.rank(method="min").astype(int)
    return int(ranks[opponent_team])


def actual_points(player_name: str, season: int, week: int) -> float | None:
    """PPR points a player actually scored in a given week (for grading past predictions)."""
    df = _weekly_data(season)
    target = normalize_name(player_name)
    mask = (df["player_display_name"].apply(normalize_name) == target) & (df["week"] == week)
    rows = df[mask]
    if rows.empty:
        return None
    return float(ppr_points(rows.iloc[-1]))


def injury_status(player_name: str, season: int, week: int) -> str | None:
    df = _injury_data(season)
    target = normalize_name(player_name)
    mask = (df["full_name"].apply(normalize_name) == target) & (df["week"] == week)
    rows = df[mask]
    if rows.empty:
        return None
    return rows.iloc[-1].get("report_status")
