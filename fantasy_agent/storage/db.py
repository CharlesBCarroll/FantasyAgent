"""SQLite storage for logged predictions, graded actuals, and learned source weights.

This is the backbone of the self-learning loop: every recommendation run logs
its blended projection per player, and once real results are known,
grading/grade.py inserts the actuals and engine/learning.py recomputes
per-source/per-position weights from the accumulated history.

Predictions/actuals are scoped per league (via `league_label`), not just per
platform — two leagues on the same platform can use different scoring
formats (PPR vs standard), so "actual points" for a given player/week isn't
a single well-defined number across leagues.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "fantasy_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    league_label TEXT NOT NULL,
    team_name TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    decision TEXT NOT NULL,           -- 'start', 'sit', or 'waiver_add'
    blended_projection REAL,
    source_breakdown TEXT,             -- JSON blob: {source_name: value}
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    league_label TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    actual_points REAL NOT NULL,
    graded_at TEXT NOT NULL,
    UNIQUE(platform, league_label, season, week, player_id)
);

CREATE TABLE IF NOT EXISTS source_weights (
    source TEXT NOT NULL,
    position TEXT NOT NULL,
    weight REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, position)
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record_prediction(
    conn: sqlite3.Connection,
    *,
    platform: str,
    league_label: str,
    team_name: str,
    season: int,
    week: int,
    player_id: str,
    player_name: str,
    position: str,
    decision: str,
    blended_projection: float | None,
    source_breakdown: str,
) -> None:
    conn.execute(
        """INSERT INTO predictions
           (platform, league_label, team_name, season, week, player_id, player_name,
            position, decision, blended_projection, source_breakdown, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            platform,
            league_label,
            team_name,
            season,
            week,
            player_id,
            player_name,
            position,
            decision,
            blended_projection,
            source_breakdown,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def record_actual(
    conn: sqlite3.Connection,
    *,
    platform: str,
    league_label: str,
    season: int,
    week: int,
    player_id: str,
    player_name: str,
    actual_points: float,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO actuals
           (platform, league_label, season, week, player_id, player_name, actual_points, graded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            platform,
            league_label,
            season,
            week,
            player_id,
            player_name,
            actual_points,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def get_ungraded_weeks(conn: sqlite3.Connection, platform: str, league_label: str, season: int) -> list[int]:
    rows = conn.execute(
        """SELECT DISTINCT p.week FROM predictions p
           WHERE p.platform = ? AND p.league_label = ? AND p.season = ?
           AND NOT EXISTS (
               SELECT 1 FROM actuals a
               WHERE a.platform = p.platform AND a.league_label = p.league_label
               AND a.season = p.season AND a.week = p.week AND a.player_id = p.player_id
           )""",
        (platform, league_label, season),
    ).fetchall()
    return sorted(r[0] for r in rows)


def get_graded_history(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT p.season, p.week, p.position, p.source_breakdown, p.blended_projection, a.actual_points
           FROM predictions p
           JOIN actuals a
             ON a.platform = p.platform AND a.league_label = p.league_label
            AND a.season = p.season AND a.week = p.week AND a.player_id = p.player_id"""
    ).fetchall()
    conn.row_factory = None
    return rows


def get_source_weights(conn: sqlite3.Connection) -> dict[tuple[str, str], float]:
    rows = conn.execute("SELECT source, position, weight FROM source_weights").fetchall()
    return {(source, position): weight for source, position, weight in rows}


def set_source_weight(conn: sqlite3.Connection, source: str, position: str, weight: float) -> None:
    conn.execute(
        """INSERT INTO source_weights (source, position, weight, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(source, position) DO UPDATE SET weight = excluded.weight, updated_at = excluded.updated_at""",
        (source, position, weight, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
