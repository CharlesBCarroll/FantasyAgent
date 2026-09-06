"""Adjust per-source, per-position blend weights from graded prediction history.

Closes the self-learning loop: sources that have historically been closer to
actual results (lower mean absolute error) get weighted more heavily in
future blends. Requires a minimum sample size before touching a weight so
early-season noise doesn't overreact.
"""

import json
from collections import defaultdict

from fantasy_agent.storage import db

MIN_SAMPLES = 3
NON_SOURCE_KEYS = {"matchup_adjustment_factor", "weather_adjustment_factor"}


def update_weights(conn, min_samples: int = MIN_SAMPLES) -> dict[tuple[str, str], float]:
    errors: dict[tuple[str, str], list[float]] = defaultdict(list)

    for row in db.get_graded_history(conn):
        position = row["position"]
        actual = row["actual_points"]
        breakdown = json.loads(row["source_breakdown"] or "{}")
        for source, value in breakdown.items():
            if source in NON_SOURCE_KEYS or value is None:
                continue
            errors[(source, position)].append(abs(value - actual))

    updated = {}
    for (source, position), errs in errors.items():
        if len(errs) < min_samples:
            continue
        mae = sum(errs) / len(errs)
        weight = 1.0 / (mae + 1.0)
        db.set_source_weight(conn, source, position, weight)
        updated[(source, position)] = weight

    return updated


def get_accuracy_summary(conn, season: int, current_week: int, weeks_back: int = 4) -> dict:
    """Recent blended-projection accuracy, for surfacing the learning loop to the user.

    Mirrors update_weights' error computation but reports the FINAL blended
    projection's error (not per-source), scoped to the last `weeks_back`
    weeks, so the report shows "how close was I lately" rather than an
    all-time average that early-season noise would dominate.
    """
    min_week = current_week - weeks_back
    position_errors: dict[str, list[float]] = defaultdict(list)
    overall_errors: list[float] = []

    for row in db.get_graded_history(conn):
        if row["season"] != season or not (min_week <= row["week"] < current_week):
            continue
        if row["blended_projection"] is None:
            continue
        error = abs(row["blended_projection"] - row["actual_points"])
        position_errors[row["position"]].append(error)
        overall_errors.append(error)

    return {
        "weeks_back": weeks_back,
        "sample_size": len(overall_errors),
        "overall_mae": sum(overall_errors) / len(overall_errors) if overall_errors else None,
        "position_mae": {
            position: sum(errs) / len(errs) for position, errs in position_errors.items()
        },
        "source_weights": {
            f"{source}/{position}": weight for (source, position), weight in db.get_source_weights(conn).items()
        },
    }
