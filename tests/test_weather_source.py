from fantasy_agent.projections.weather_source import weather_adjustment


def test_dome_is_always_neutral():
    assert weather_adjustment({"is_dome": True}, "QB") == 1.0


def test_no_weather_data_is_neutral():
    assert weather_adjustment(None, "QB") == 1.0


def test_rb_unaffected_by_wind():
    assert weather_adjustment({"is_dome": False, "wind_speed_mph": 30, "precipitation_mm": 5}, "RB") == 1.0


def test_high_wind_discounts_pass_dependent_positions():
    factor = weather_adjustment({"is_dome": False, "wind_speed_mph": 25, "precipitation_mm": 0}, "QB")
    assert factor == 0.85


def test_moderate_wind_smaller_discount():
    factor = weather_adjustment({"is_dome": False, "wind_speed_mph": 17, "precipitation_mm": 0}, "WR")
    assert factor == 0.93


def test_low_wind_no_discount():
    factor = weather_adjustment({"is_dome": False, "wind_speed_mph": 5, "precipitation_mm": 0}, "TE")
    assert factor == 1.0


def test_heavy_precipitation_adds_discount():
    factor = weather_adjustment({"is_dome": False, "wind_speed_mph": 5, "precipitation_mm": 3}, "K")
    assert factor == 0.95


def test_wind_and_precipitation_discounts_compound():
    factor = weather_adjustment({"is_dome": False, "wind_speed_mph": 25, "precipitation_mm": 3}, "QB")
    assert round(factor, 4) == round(0.85 * 0.95, 4)
