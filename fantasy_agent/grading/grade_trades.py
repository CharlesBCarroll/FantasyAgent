"""Grade past trade suggestions: would accepting them have actually helped?

Runs a few weeks after a trade is suggested (once enough games have been
played to judge it) — sums actual points scored by both sides' named players
over the weeks since the suggestion, using the same actual_points signal
used to grade start/sit predictions.
"""

from fantasy_agent.projections import nfl_data_source
from fantasy_agent.storage import db

GRADE_AFTER_WEEKS = 3


def grade_pending_trades(
    conn,
    platform: str,
    league_label: str,
    season: int,
    current_week: int,
    scoring: str | dict | None = None,
    grade_after_weeks: int = GRADE_AFTER_WEEKS,
) -> int:
    resolved_scoring = nfl_data_source.resolve_scoring(scoring)
    pending = db.get_pending_trade_suggestions(conn, platform, league_label, season, current_week, grade_after_weeks)

    for row in pending:
        weeks = range(row["week_suggested"], current_week)
        give_total = sum(
            nfl_data_source.actual_points(row["give_player_name"], season, w, resolved_scoring) or 0.0
            for w in weeks
        )
        get_total = sum(
            nfl_data_source.actual_points(row["get_player_name"], season, w, resolved_scoring) or 0.0
            for w in weeks
        )
        db.record_trade_grade(conn, row["id"], give_total, get_total)

    return len(pending)
