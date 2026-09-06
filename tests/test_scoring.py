from fantasy_agent.projections.nfl_data_source import fantasy_points, resolve_scoring


def make_row(**overrides):
    row = {
        "passing_yards": 0,
        "passing_tds": 0,
        "interceptions": 0,
        "rushing_yards": 0,
        "rushing_tds": 0,
        "receptions": 0,
        "receiving_yards": 0,
        "receiving_tds": 0,
        "fumbles_lost": 0,
    }
    row.update(overrides)
    return row


def test_resolve_scoring_defaults_to_full_ppr():
    scoring = resolve_scoring(None)
    assert scoring["reception"] == 1.0


def test_resolve_scoring_preset_names():
    assert resolve_scoring("standard")["reception"] == 0.0
    assert resolve_scoring("half_ppr")["reception"] == 0.5
    assert resolve_scoring("ppr")["reception"] == 1.0


def test_resolve_scoring_custom_override():
    scoring = resolve_scoring({"reception": 0.25, "pass_td": 6})
    assert scoring["reception"] == 0.25
    assert scoring["pass_td"] == 6
    assert scoring["rush_td"] == 6  # untouched default preserved


def test_fantasy_points_reception_value_changes_by_format():
    row = make_row(receptions=10, receiving_yards=50)
    ppr_points = fantasy_points(row, resolve_scoring("ppr"))
    standard_points = fantasy_points(row, resolve_scoring("standard"))
    half_ppr_points = fantasy_points(row, resolve_scoring("half_ppr"))

    assert ppr_points == 15.0  # 10 receptions + 5 yardage points
    assert standard_points == 5.0
    assert half_ppr_points == 10.0
