import pandas as pd

from fantasy_agent.projections import nfl_data_source


def _fake_schedule():
    return pd.DataFrame(
        [
            {"week": 1, "home_team": "BUF", "away_team": "KC"},
            {"week": 4, "home_team": "BUF", "away_team": "MIA"},
            {"week": 5, "home_team": "NYJ", "away_team": "BUF"},
            {"week": 6, "home_team": "BUF", "away_team": "NE"},
            {"week": 7, "home_team": "LAR", "away_team": "BUF"},
        ]
    )


def test_rest_of_season_matchups_finds_next_n_opponents_home_and_away(monkeypatch):
    monkeypatch.setattr(nfl_data_source, "_schedule", lambda season: _fake_schedule())
    monkeypatch.setattr(nfl_data_source, "opponent_defense_rank", lambda *a, **k: None)

    matchups = nfl_data_source.rest_of_season_matchups(
        "WR", "BUF", season=2026, from_week=3, scoring={}, lookback_weeks=3
    )
    assert [m["week"] for m in matchups] == [4, 5, 6]
    assert [m["opponent"] for m in matchups] == ["MIA", "NYJ", "NE"]


def test_rest_of_season_matchups_labels_by_defense_rank(monkeypatch):
    monkeypatch.setattr(nfl_data_source, "_schedule", lambda season: _fake_schedule())
    ranks = {"MIA": 3, "NYJ": 16, "NE": 30}
    monkeypatch.setattr(
        nfl_data_source, "opponent_defense_rank", lambda position, opponent, *a, **k: ranks[opponent]
    )

    matchups = nfl_data_source.rest_of_season_matchups(
        "WR", "BUF", season=2026, from_week=3, scoring={}, lookback_weeks=3
    )
    labels = {m["opponent"]: m["label"] for m in matchups}
    assert labels == {"MIA": "tough", "NYJ": "neutral", "NE": "soft"}
