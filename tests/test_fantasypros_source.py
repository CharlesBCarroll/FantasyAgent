from fantasy_agent.projections import fantasypros_source


def test_get_projection_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("FANTASYPROS_API_KEY", raising=False)
    fantasypros_source._projections_cache.clear()
    assert fantasypros_source.get_projection("Some Player", 2026, 3) is None


def test_get_projection_returns_none_on_request_failure(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros_source._projections_cache.clear()

    def broken_get(*args, **kwargs):
        raise ConnectionError("no network in tests")

    monkeypatch.setattr(fantasypros_source.requests, "get", broken_get)
    assert fantasypros_source.get_projection("Some Player", 2026, 3) is None


def test_scoring_param_maps_presets():
    assert fantasypros_source._scoring_param("ppr") == "PPR"
    assert fantasypros_source._scoring_param("half_ppr") == "HALF"
    assert fantasypros_source._scoring_param("standard") == "STD"
    assert fantasypros_source._scoring_param(None) == "PPR"
    assert fantasypros_source._scoring_param({"reception": 0.5}) == "PPR"
