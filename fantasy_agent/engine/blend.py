"""Combine multiple projection signals into one point estimate per player.

Weights start equal across sources and are only overridden once
engine/learning.py has enough graded history to say one source is more
reliable than another for a given position.
"""

DEFAULT_WEIGHT = 1.0
TOTAL_NFL_TEAMS = 32


def blend(
    sources: dict[str, float | None],
    position: str,
    weights: dict[tuple[str, str], float] | None = None,
) -> tuple[float | None, dict[str, float]]:
    """Weighted average of available (non-None) source values.

    Returns (blended_value_or_None, {source: value_used}) — the breakdown is
    logged alongside the prediction so learning.py can later attribute error
    back to individual sources.
    """
    weights = weights or {}
    available = {name: value for name, value in sources.items() if value is not None}
    if not available:
        return None, {}

    total_weight = 0.0
    weighted_sum = 0.0
    for name, value in available.items():
        w = weights.get((name, position), DEFAULT_WEIGHT)
        weighted_sum += value * w
        total_weight += w

    if total_weight == 0:
        return None, available

    return weighted_sum / total_weight, available


def matchup_adjustment(defense_rank: int | None, total_teams: int = TOTAL_NFL_TEAMS) -> float:
    """Scale a projection by opponent strength: rank 1 (toughest) -> 0.85x, rank N (softest) -> 1.15x."""
    if defense_rank is None or total_teams <= 1:
        return 1.0
    percentile = (defense_rank - 1) / (total_teams - 1)
    return 0.85 + percentile * 0.30
