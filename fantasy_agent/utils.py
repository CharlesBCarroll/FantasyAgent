"""Small shared helpers used across platform/projection/engine modules."""

import re
from datetime import date

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def current_week(season: int) -> int:
    """Best-effort current NFL week from the nflverse schedule for `season`."""
    import nfl_data_py as nfl
    import pandas as pd

    schedule = nfl.import_schedules([season])
    schedule["gameday"] = pd.to_datetime(schedule["gameday"]).dt.date
    today = date.today()
    upcoming = schedule[schedule["gameday"] >= today]
    if not upcoming.empty:
        return int(upcoming["week"].min())
    return int(schedule["week"].max())


# ESPN's proTeam abbreviations differ from nflverse's team abbreviations for
# two franchises; every other team matches between the two conventions.
_ESPN_TO_NFLVERSE_TEAM = {"LAR": "LA", "WSH": "WAS"}


def normalize_team_abbr(team: str) -> str:
    """Map an ESPN team abbreviation to nflverse's convention, if they differ."""
    return _ESPN_TO_NFLVERSE_TEAM.get(team, team)


def normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching across data sources.

    Different providers spell names slightly differently (periods, suffixes,
    apostrophes), so exact string equality is unreliable for joining data
    across Yahoo/ESPN/Sleeper/nflverse.
    """
    cleaned = re.sub(r"[.'`]", "", name.lower())
    tokens = [t for t in re.split(r"[\s-]+", cleaned) if t and t not in _SUFFIXES]
    return " ".join(tokens)
