"""Outdoor-game weather signal via Open-Meteo (free, no auth required).

Forecasts are only meaningfully accurate roughly two weeks out, so this
gracefully falls back to "no data" (neutral adjustment) for games too far in
the future or for any network hiccup — same fallback pattern used throughout
projections/. Domed/indoor stadiums are always treated as neutral.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import nfl_data_py as nfl
import pandas as pd
import requests

from fantasy_agent.utils import normalize_team_abbr

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# (latitude, longitude, is_dome) per nflverse home-team abbreviation.
NFL_STADIUMS = {
    "ARI": (33.5276, -112.2626, True),
    "ATL": (33.7554, -84.4008, True),
    "BAL": (39.2780, -76.6227, False),
    "BUF": (42.7738, -78.7869, False),
    "CAR": (35.2258, -80.8528, False),
    "CHI": (41.8623, -87.6167, False),
    "CIN": (39.0954, -84.5160, False),
    "CLE": (41.5061, -81.6995, False),
    "DAL": (32.7473, -97.0945, True),
    "DEN": (39.7439, -105.0201, False),
    "DET": (42.3400, -83.0456, True),
    "GB": (44.5013, -88.0622, False),
    "HOU": (29.6847, -95.4107, True),
    "IND": (39.7601, -86.1639, True),
    "JAX": (30.3239, -81.6373, False),
    "KC": (39.0489, -94.4839, False),
    "LA": (33.9535, -118.3392, True),
    "LAC": (33.9535, -118.3392, True),
    "LV": (36.0909, -115.1833, True),
    "MIA": (25.9580, -80.2389, False),
    "MIN": (44.9738, -93.2578, True),
    "NE": (42.0909, -71.2643, False),
    "NO": (29.9509, -90.0815, True),
    "NYG": (40.8135, -74.0745, False),
    "NYJ": (40.8135, -74.0745, False),
    "PHI": (39.9008, -75.1675, False),
    "PIT": (40.4468, -80.0158, False),
    "SEA": (47.5952, -122.3316, False),
    "SF": (37.4032, -121.9698, False),
    "TB": (27.9759, -82.5033, False),
    "TEN": (36.1665, -86.7713, False),
    "WAS": (38.9078, -76.8645, False),
}

WIND_DISCOUNT_POSITIONS = {"QB", "WR", "TE", "K"}

_schedule_cache: dict[int, pd.DataFrame] = {}


def _schedule(season: int) -> pd.DataFrame:
    if season not in _schedule_cache:
        _schedule_cache[season] = nfl.import_schedules([season])
    return _schedule_cache[season]


def get_game_weather(season: int, week: int, nfl_team: str) -> dict | None:
    """Weather at this team's game this week. None means "no adjustment" (dome/unavailable)."""
    team = normalize_team_abbr(nfl_team)
    schedule = _schedule(season)
    game = schedule[
        (schedule["week"] == week) & ((schedule["home_team"] == team) | (schedule["away_team"] == team))
    ]
    if game.empty:
        return None

    row = game.iloc[0]
    stadium = NFL_STADIUMS.get(row["home_team"])
    if stadium is None:
        return None
    lat, lon, is_dome = stadium
    if is_dome:
        return {"is_dome": True}

    try:
        game_date = pd.to_datetime(row["gameday"]).date()
        hour, minute = (int(x) for x in str(row.get("gametime") or "13:00").split(":")[:2])
        local_kickoff = datetime(
            game_date.year, game_date.month, game_date.day, hour, minute, tzinfo=ZoneInfo("America/New_York")
        )
        kickoff_utc = local_kickoff.astimezone(ZoneInfo("UTC"))

        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "wind_speed_10m,precipitation",
                "wind_speed_unit": "mph",
                "start_date": game_date.isoformat(),
                "end_date": game_date.isoformat(),
                "timezone": "UTC",
            },
            timeout=10,
        )
        resp.raise_for_status()
        hourly = resp.json()["hourly"]
        times = [datetime.fromisoformat(t).replace(tzinfo=ZoneInfo("UTC")) for t in hourly["time"]]
        closest = min(range(len(times)), key=lambda i: abs((times[i] - kickoff_utc).total_seconds()))
        return {
            "is_dome": False,
            "wind_speed_mph": hourly["wind_speed_10m"][closest],
            "precipitation_mm": hourly["precipitation"][closest],
        }
    except Exception:
        return None


def weather_adjustment(weather: dict | None, position: str) -> float:
    """Multiplicative factor discounting pass-dependent positions in bad outdoor weather."""
    if not weather or weather.get("is_dome") or position not in WIND_DISCOUNT_POSITIONS:
        return 1.0

    factor = 1.0
    wind = weather.get("wind_speed_mph", 0)
    if wind >= 20:
        factor *= 0.85
    elif wind >= 15:
        factor *= 0.93

    if weather.get("precipitation_mm", 0) >= 2:
        factor *= 0.95

    return factor
