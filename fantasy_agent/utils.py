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


def normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching across data sources.

    Different providers spell names slightly differently (periods, suffixes,
    apostrophes), so exact string equality is unreliable for joining data
    across Yahoo/ESPN/Sleeper/nflverse.
    """
    cleaned = re.sub(r"[.'`]", "", name.lower())
    tokens = [t for t in re.split(r"[\s-]+", cleaned) if t and t not in _SUFFIXES]
    return " ".join(tokens)
