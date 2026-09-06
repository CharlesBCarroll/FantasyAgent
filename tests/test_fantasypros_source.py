from fantasy_agent.projections import fantasypros_source


def test_get_projection_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("FANTASYPROS_API_KEY", raising=False)
    fantasypros_source._projections_cache.clear()
    assert fantasypros_source.get_projection("Some Player", "RB", 2026, 3) is None


def test_get_projection_returns_none_on_request_failure(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros_source._projections_cache.clear()

    def broken_get(*args, **kwargs):
        raise ConnectionError("no network in tests")

    monkeypatch.setattr(fantasypros_source.requests, "get", broken_get)
    assert fantasypros_source.get_projection("Some Player", "RB", 2026, 3) is None


def test_get_projection_returns_none_for_unmapped_position(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros_source._projections_cache.clear()
    assert fantasypros_source.get_projection("Some Player", "P", 2026, 3) is None


def test_get_projection_picks_stats_field_by_scoring(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros_source._projections_cache.clear()

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "players": [
                    {"name": "Star Back", "stats": {"points": 10.0, "points_ppr": 15.0, "points_half": 12.5}}
                ]
            }

    monkeypatch.setattr(fantasypros_source.requests, "get", lambda *a, **k: FakeResponse())

    assert fantasypros_source.get_projection("Star Back", "RB", 2026, 3, scoring="ppr") == 15.0
    assert fantasypros_source.get_projection("Star Back", "RB", 2026, 3, scoring="standard") == 10.0
    assert fantasypros_source.get_projection("Star Back", "RB", 2026, 3, scoring="half_ppr") == 12.5


def test_get_projection_returns_none_when_player_not_in_top_10(monkeypatch):
    monkeypatch.setenv("FANTASYPROS_API_KEY", "fake-key")
    fantasypros_source._projections_cache.clear()

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"players": [{"name": "Star Back", "stats": {"points_ppr": 15.0}}]}

    monkeypatch.setattr(fantasypros_source.requests, "get", lambda *a, **k: FakeResponse())
    assert fantasypros_source.get_projection("Bench Warmer", "RB", 2026, 3) is None
