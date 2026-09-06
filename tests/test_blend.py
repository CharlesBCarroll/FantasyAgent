from fantasy_agent.engine.blend import blend, matchup_adjustment


def test_blend_averages_available_sources_with_equal_default_weight():
    blended, breakdown = blend({"native": 10.0, "trend": 20.0}, "RB", weights=None)
    assert blended == 15.0
    assert breakdown == {"native": 10.0, "trend": 20.0}


def test_blend_ignores_missing_sources():
    blended, breakdown = blend({"native": 12.0, "trend": None}, "WR", weights=None)
    assert blended == 12.0
    assert breakdown == {"native": 12.0}


def test_blend_returns_none_when_no_sources_available():
    blended, breakdown = blend({"native": None, "trend": None}, "TE", weights=None)
    assert blended is None
    assert breakdown == {}


def test_blend_respects_learned_weights():
    weights = {("native", "RB"): 3.0, ("trend", "RB"): 1.0}
    blended, _ = blend({"native": 20.0, "trend": 0.0}, "RB", weights=weights)
    assert blended == 15.0  # (20*3 + 0*1) / 4


def test_matchup_adjustment_toughest_defense_scales_down():
    assert matchup_adjustment(1, total_teams=32) == 0.85


def test_matchup_adjustment_softest_defense_scales_up():
    assert matchup_adjustment(32, total_teams=32) == 1.15


def test_matchup_adjustment_unknown_rank_is_neutral():
    assert matchup_adjustment(None) == 1.0
