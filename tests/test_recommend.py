import pytest

from fantasy_agent.engine.recommend import (
    generate_lineup_recommendations,
    generate_waiver_recommendations,
    project_player,
    suggest_handcuffs,
)
from fantasy_agent.platforms.base import FreeAgent, Player, Roster


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # recent_trend / opponent_defense_rank / Sleeper trending / weather normally hit the network; keep tests offline.
    monkeypatch.setattr("fantasy_agent.projections.nfl_data_source.recent_trend", lambda *a, **k: None)
    monkeypatch.setattr("fantasy_agent.projections.nfl_data_source.opponent_defense_rank", lambda *a, **k: None)
    monkeypatch.setattr("fantasy_agent.projections.sleeper_source.get_trending", lambda *a, **k: {})
    monkeypatch.setattr("fantasy_agent.projections.weather_source.get_game_weather", lambda *a, **k: None)


def make_player(name, position, slot, status="ACTIVE", native_projection=10.0, eligible_slots=None):
    return Player(
        platform="espn",
        player_id=name.replace(" ", "_"),
        name=name,
        position=position,
        nfl_team="KC",
        lineup_slot=slot,
        status=status,
        native_projection=native_projection,
        eligible_slots=eligible_slots or [slot],
    )


def test_project_player_uses_native_projection_when_trend_unavailable():
    player = make_player("Test Back", "RB", "RB", native_projection=14.0)
    blended, breakdown = project_player(player, season=2026, week=3, weights=None)
    assert blended == 14.0
    assert breakdown == {"native": 14.0}


def test_status_alert_flagged_for_questionable_starter():
    starter = make_player("Hurt Guy", "WR", "WR", status="QUESTIONABLE", native_projection=10.0)
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[starter])
    rec = generate_lineup_recommendations(roster, season=2026, week=3, weights=None)
    assert len(rec["status_alerts"]) == 1
    assert rec["status_alerts"][0]["name"] == "Hurt Guy"


def test_trending_down_alert_flagged_for_rostered_player_being_dropped(monkeypatch):
    monkeypatch.setattr(
        "fantasy_agent.projections.sleeper_source.get_trending",
        lambda direction="add", **k: {"cold bench guy": 5000} if direction == "drop" else {},
    )
    bench = make_player("Cold Bench Guy", "RB", "BN", native_projection=3.0)
    other = make_player("Fine Player", "RB", "RB", native_projection=10.0)
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[bench, other])
    rec = generate_lineup_recommendations(roster, season=2026, week=3, weights=None)
    assert len(rec["trending_down_alerts"]) == 1
    assert rec["trending_down_alerts"][0]["name"] == "Cold Bench Guy"
    assert rec["trending_down_alerts"][0]["drop_count"] == 5000


def test_swap_suggested_when_bench_player_clearly_outprojects_starter():
    starter = make_player("Weak Starter", "RB", "RB", native_projection=5.0)
    bench = make_player("Strong Bench", "RB", "BN", native_projection=12.0, eligible_slots=["RB", "BN"])
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[starter, bench])
    rec = generate_lineup_recommendations(roster, season=2026, week=3, weights=None)
    assert len(rec["start_sit_swaps"]) == 1
    swap = rec["start_sit_swaps"][0]
    assert swap["start"] == "Strong Bench"
    assert swap["sit"] == "Weak Starter"


def test_close_call_flagged_for_small_margin():
    starter = make_player("Starter", "RB", "RB", native_projection=10.0)
    bench = make_player("Bench Guy", "RB", "BN", native_projection=11.0, eligible_slots=["RB", "BN"])
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[starter, bench])
    rec = generate_lineup_recommendations(roster, season=2026, week=3, weights=None)
    assert rec["start_sit_swaps"] == []
    assert len(rec["close_calls"]) == 1


def test_waiver_recommendation_flags_upgrade_over_weakest_rostered():
    starter = make_player("Weak WR", "WR", "WR", native_projection=6.0)
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[starter])
    agent = FreeAgent(
        platform="espn",
        player_id="fa1",
        name="Hot Waiver Add",
        position="WR",
        nfl_team="BUF",
        native_projection=15.0,
    )
    waivers = generate_waiver_recommendations(roster, [agent], season=2026, week=3, weights=None)
    assert waivers["WR"][0]["name"] == "Hot Waiver Add"
    assert waivers["WR"][0]["beats_weakest_rostered"] is True


def test_waiver_recommendation_surfaces_sleeper_trending_adds(monkeypatch):
    monkeypatch.setattr(
        "fantasy_agent.projections.sleeper_source.get_trending",
        lambda *a, **k: {"hot waiver add": 12345},
    )
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[])
    agent = FreeAgent(
        platform="espn",
        player_id="fa1",
        name="Hot Waiver Add",
        position="WR",
        nfl_team="BUF",
        native_projection=15.0,
    )
    waivers = generate_waiver_recommendations(roster, [agent], season=2026, week=3, weights=None)
    assert waivers["WR"][0]["trending_adds"] == 12345


def test_waiver_recommendation_trending_adds_is_none_when_not_trending():
    roster = Roster(platform="espn", team_name="My Team", week=3, players=[])
    agent = FreeAgent(
        platform="espn",
        player_id="fa1",
        name="Quiet Player",
        position="WR",
        nfl_team="BUF",
        native_projection=15.0,
    )
    waivers = generate_waiver_recommendations(roster, [agent], season=2026, week=3, weights=None)
    assert waivers["WR"][0]["trending_adds"] is None


def test_suggest_handcuffs_picks_best_same_team_same_position_free_agent():
    injured = make_player("Injured RB", "RB", "RB", status="OUT", native_projection=15.0)
    injured.nfl_team = "BUF"
    status_alerts = [
        {"player_id": injured.player_id, "name": injured.name, "status": "OUT", "lineup_slot": "RB"}
    ]
    weak_backup = FreeAgent(
        platform="espn", player_id="fa1", name="Weak Backup", position="RB", nfl_team="BUF", native_projection=5.0
    )
    strong_backup = FreeAgent(
        platform="espn", player_id="fa2", name="Strong Backup", position="RB", nfl_team="BUF", native_projection=9.0
    )
    wrong_team = FreeAgent(
        platform="espn", player_id="fa3", name="Wrong Team RB", position="RB", nfl_team="KC", native_projection=20.0
    )
    handcuffs = suggest_handcuffs(
        status_alerts, [injured], [weak_backup, strong_backup, wrong_team], season=2026, week=3, weights=None
    )
    assert handcuffs[injured.player_id]["name"] == "Strong Backup"


def test_suggest_handcuffs_skips_questionable_status():
    questionable = make_player("Maybe Guy", "RB", "RB", status="QUESTIONABLE", native_projection=15.0)
    status_alerts = [
        {"player_id": questionable.player_id, "name": questionable.name, "status": "QUESTIONABLE", "lineup_slot": "RB"}
    ]
    backup = FreeAgent(
        platform="espn", player_id="fa1", name="Backup", position="RB", nfl_team="KC", native_projection=9.0
    )
    handcuffs = suggest_handcuffs(status_alerts, [questionable], [backup], season=2026, week=3, weights=None)
    assert handcuffs == {}
