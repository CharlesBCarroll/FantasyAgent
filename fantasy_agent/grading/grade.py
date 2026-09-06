"""Grade previously logged predictions against actual results once games are final.

Runs before each new recommendation pass so the learning loop stays current:
find weeks with predictions but no recorded actuals, pull real PPR points for
each predicted player from nflverse data, and trigger a weight update.
"""

from fantasy_agent.engine import learning
from fantasy_agent.projections import nfl_data_source
from fantasy_agent.storage import db


def grade_pending_weeks(conn, platform: str, season: int, current_week_num: int) -> int:
    """Grade any fully-played weeks with ungraded predictions. Returns players graded."""
    pending_weeks = [w for w in db.get_ungraded_weeks(conn, platform, season) if w < current_week_num]

    graded_count = 0
    for week in pending_weeks:
        rows = conn.execute(
            "SELECT DISTINCT player_id, player_name FROM predictions "
            "WHERE platform = ? AND season = ? AND week = ?",
            (platform, season, week),
        ).fetchall()
        for player_id, player_name in rows:
            points = nfl_data_source.actual_points(player_name, season, week)
            if points is None:
                continue
            db.record_actual(
                conn,
                platform=platform,
                season=season,
                week=week,
                player_id=player_id,
                player_name=player_name,
                actual_points=points,
            )
            graded_count += 1

    if graded_count:
        learning.update_weights(conn)

    return graded_count
