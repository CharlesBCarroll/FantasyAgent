"""Historical/context signals derived from nflverse data.

nfl_data_py's bundled URLs point at nflverse's deprecated "player_stats"
release (retired 2025-08-01 in favor of "stats_player"/"stats_team"), so we
fetch directly from the current nflverse-data release assets instead of
using nfl_data_py's import_weekly_data/import_injuries helpers.

This has no forward-looking projections either — it's actual/historical
stats. We derive two signals from it: a recent-performance trend (proxy for
"current form") and an opponent-defense-strength rank (proxy for matchup
difficulty). Both feed blend.py alongside each platform's own native
projection (which already reflects the league's real scoring settings).
Since these signals are computed from raw stats, they must use the same
scoring format as the league they're being used for, or they'll
systematically mislead a non-PPR/half-PPR league.
"""

import sys

import nfl_data_py as nfl
import pandas as pd

from fantasy_agent.utils import normalize_name, normalize_team_abbr

WEEKLY_STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.parquet"
INJURIES_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.parquet"

_WEEKLY_COLUMNS = [
    "player_display_name",
    "week",
    "position",
    "opponent_team",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "sack_fumbles_lost",
    "rushing_fumbles_lost",
    "receiving_fumbles_lost",
]
_INJURY_COLUMNS = ["full_name", "week", "report_status"]

_weekly_cache: dict[int, pd.DataFrame] = {}
_injury_cache: dict[int, pd.DataFrame] = {}
_schedule_cache: dict[int, pd.DataFrame] = {}

DEFENSE_RANK_TOTAL_TEAMS = 32
SOFT_MATCHUP_RANK = 23  # rank >= this allows the most fantasy points (softest matchup)
TOUGH_MATCHUP_RANK = 10  # rank <= this allows the fewest fantasy points (toughest matchup)

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
    fumbles_lost = (
        row.get("sack_fumbles_lost", 0)
        + row.get("rushing_fumbles_lost", 0)
        + row.get("receiving_fumbles_lost", 0)
    )
    return (
        row.get("passing_yards", 0) / scoring["pass_yd_per_point"]
        + row.get("passing_tds", 0) * scoring["pass_td"]
        + row.get("passing_interceptions", 0) * scoring["interception"]
        + row.get("rushing_yards", 0) / scoring["rush_yd_per_point"]
        + row.get("rushing_tds", 0) * scoring["rush_td"]
        + row.get("receptions", 0) * scoring["reception"]
        + row.get("receiving_yards", 0) / scoring["rec_yd_per_point"]
        + row.get("receiving_tds", 0) * scoring["rec_td"]
        + fumbles_lost * scoring["fumble_lost"]
    )


def _fetch_parquet(url: str, empty_columns: list[str], season: int, what: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(url)
    except Exception as exc:
        print(
            f"[nfl_data_source] no {what} data available yet for {season} ({exc}); "
            "falling back to native projections only for this signal.",
            file=sys.stderr,
        )
        return pd.DataFrame(columns=empty_columns)


def _weekly_data(season: int) -> pd.DataFrame:
    if season not in _weekly_cache:
        _weekly_cache[season] = _fetch_parquet(
            WEEKLY_STATS_URL.format(season=season), _WEEKLY_COLUMNS, season, "weekly stats"
        )
    return _weekly_cache[season]


def _injury_data(season: int) -> pd.DataFrame:
    if season not in _injury_cache:
        _injury_cache[season] = _fetch_parquet(
            INJURIES_URL.format(season=season), _INJURY_COLUMNS, season, "injury report"
        )
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


def _schedule(season: int) -> pd.DataFrame:
    if season not in _schedule_cache:
        _schedule_cache[season] = nfl.import_schedules([season])
    return _schedule_cache[season]


def _matchup_label(rank: int | None) -> str:
    if rank is None:
        return "unknown"
    if rank <= TOUGH_MATCHUP_RANK:
        return "tough"
    if rank >= SOFT_MATCHUP_RANK:
        return "soft"
    return "neutral"


def rest_of_season_matchups(
    position: str, nfl_team: str, season: int, from_week: int, scoring: dict, lookback_weeks: int = 3
) -> list[dict]:
    """This team's next `lookback_weeks` opponents and how tough each is for `position`.

    Defense strength is evaluated using data available as of `from_week` for
    every future matchup (there's no way to know a future week's actual
    defensive performance in advance) — this answers "given what we know
    now, which of the next few matchups look softest," not a live forecast.
    """
    team = normalize_team_abbr(nfl_team)
    schedule = _schedule(season)
    upcoming = (
        schedule[
            (schedule["week"] > from_week) & ((schedule["home_team"] == team) | (schedule["away_team"] == team))
        ]
        .sort_values("week")
        .head(lookback_weeks)
    )

    matchups = []
    for _, row in upcoming.iterrows():
        opponent = row["away_team"] if row["home_team"] == team else row["home_team"]
        rank = opponent_defense_rank(position, opponent, season, from_week, scoring)
        matchups.append({"week": int(row["week"]), "opponent": opponent, "defense_rank": rank, "label": _matchup_label(rank)})
    return matchups


def injury_status(player_name: str, season: int, week: int) -> str | None:
    df = _injury_data(season)
    target = normalize_name(player_name)
    mask = (df["full_name"].apply(normalize_name) == target) & (df["week"] == week)
    rows = df[mask]
    if rows.empty:
        return None
    return rows.iloc[-1].get("report_status")
