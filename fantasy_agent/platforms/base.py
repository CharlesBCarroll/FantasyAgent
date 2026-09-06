"""Platform-agnostic data model shared by every downstream component.

Yahoo and ESPN clients translate their native API responses into these
dataclasses so nothing in engine/ or reporting/ ever has to branch on
which platform a player came from.
"""

from dataclasses import dataclass, field


@dataclass
class Player:
    platform: str  # "yahoo" or "espn"
    player_id: str
    name: str
    position: str  # QB, RB, WR, TE, K, DEF, FLEX-eligible etc.
    nfl_team: str  # e.g. "KC"
    lineup_slot: str  # e.g. "BN", "RB", "FLEX", "IR"
    status: str  # "ACTIVE", "QUESTIONABLE", "OUT", "DOUBTFUL", "BYE", "IR"
    opponent: str | None = None  # this week's NFL opponent, e.g. "@BUF"
    native_projection: float | None = None  # platform's own projected points, if any
    eligible_slots: list[str] = field(default_factory=list)

    @property
    def is_starter(self) -> bool:
        return self.lineup_slot not in ("BN", "IR")


@dataclass
class Roster:
    platform: str
    team_name: str
    week: int
    players: list[Player]

    def starters(self) -> list[Player]:
        return [p for p in self.players if p.is_starter]

    def bench(self) -> list[Player]:
        return [p for p in self.players if not p.is_starter]


@dataclass
class Matchup:
    platform: str
    week: int
    team_name: str
    opponent_name: str
    team_projected: float | None = None
    opponent_projected: float | None = None


@dataclass
class FreeAgent:
    platform: str
    player_id: str
    name: str
    position: str
    nfl_team: str
    percent_owned: float | None = None
    native_projection: float | None = None
    opponent: str | None = None
