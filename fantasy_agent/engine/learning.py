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
NON_SOURCE_KEYS = {"matchup_adjustment_factor"}


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
