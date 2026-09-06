import json
from pathlib import Path

import pytest

from fantasy_agent.engine import learning
from fantasy_agent.storage import db


@pytest.fixture
def conn(tmp_path: Path):
    connection = db.get_connection(tmp_path / "test.db")
    db.init_db(connection)
    yield connection
    connection.close()


def _log_prediction_and_actual(conn, week, blended, actual, position="RB"):
    db.record_prediction(
        conn,
        platform="espn",
        league_label="League A",
        team_name="My Team",
        season=2026,
        week=week,
        player_id=f"p{week}",
        player_name=f"Player {week}",
        position=position,
        decision="start",
        blended_projection=blended,
        source_breakdown=json.dumps({"native": blended}),
    )
    db.record_actual(
        conn,
        platform="espn",
        league_label="League A",
        season=2026,
        week=week,
        player_id=f"p{week}",
        player_name=f"Player {week}",
        actual_points=actual,
    )


def test_accuracy_summary_empty_when_no_history(conn):
    summary = learning.get_accuracy_summary(conn, season=2026, current_week=5)
    assert summary["sample_size"] == 0
    assert summary["overall_mae"] is None


def test_accuracy_summary_computes_mae_within_window(conn):
    _log_prediction_and_actual(conn, week=1, blended=10.0, actual=12.0)  # error 2, outside window
    _log_prediction_and_actual(conn, week=4, blended=10.0, actual=14.0)  # error 4, inside window
    summary = learning.get_accuracy_summary(conn, season=2026, current_week=5, weeks_back=1)
    assert summary["sample_size"] == 1
    assert summary["overall_mae"] == 4.0
    assert summary["position_mae"]["RB"] == 4.0


def test_accuracy_summary_excludes_current_week(conn):
    _log_prediction_and_actual(conn, week=5, blended=10.0, actual=99.0)
    summary = learning.get_accuracy_summary(conn, season=2026, current_week=5, weeks_back=4)
    assert summary["sample_size"] == 0
