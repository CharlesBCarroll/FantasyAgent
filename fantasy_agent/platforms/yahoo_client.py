"""Yahoo Fantasy Football client, wrapping yfpy into the common data model.

NOTE: yfpy's exact method names have shifted across major versions. The calls
below match yfpy 16.x's documented API but should be spot-checked against
whatever version actually gets installed during the live smoke test.
"""

import os
from pathlib import Path

from yfpy.query import YahooFantasySportsQuery

from fantasy_agent.platforms.base import FreeAgent, Matchup, Player, Roster

SECRETS_DIR = Path(__file__).resolve().parents[2] / "secrets"

STATUS_MAP = {
    "Q": "QUESTIONABLE",
    "O": "OUT",
    "D": "DOUBTFUL",
    "IR": "IR",
    "BYE": "BYE",
}


def _parse_team_key(team_key: str) -> tuple[str, str]:
    # "423.l.12345.t.1" -> ("12345", "1")
    parts = team_key.split(".")
    return parts[2], parts[4]


def get_query(config: dict) -> YahooFantasySportsQuery:
    league_id, _team_id = _parse_team_key(config["yahoo"]["team_key"])
    return YahooFantasySportsQuery(
        league_id=league_id,
        game_code="nfl",
        yahoo_consumer_key=os.environ["YAHOO_CLIENT_ID"],
        yahoo_consumer_secret=os.environ["YAHOO_CLIENT_SECRET"],
        env_file_location=SECRETS_DIR,
        save_token_data_to_env_file=True,
    )


def _to_player(p) -> Player:
    return Player(
        platform="yahoo",
        player_id=str(p.player_id),
        name=p.name.full,
        position=p.display_position,
        nfl_team=(p.editorial_team_abbr or "").upper(),
        lineup_slot=p.selected_position.position if p.selected_position else "BN",
        status=STATUS_MAP.get(getattr(p, "status", None), "ACTIVE"),
        eligible_slots=list(getattr(p, "eligible_positions", []) or []),
    )


def get_roster(config: dict, week: int) -> Roster:
    query = get_query(config)
    _league_id, team_id = _parse_team_key(config["yahoo"]["team_key"])
    roster = query.get_team_roster_by_week(team_id, week)
    team_info = query.get_team_info(team_id)
    players = [_to_player(p) for p in roster.players]
    return Roster(platform="yahoo", team_name=team_info.name, week=week, players=players)


def get_matchup(config: dict, week: int) -> Matchup:
    query = get_query(config)
    _league_id, team_id = _parse_team_key(config["yahoo"]["team_key"])
    scoreboard = query.get_league_scoreboard_by_week(week)
    for matchup in scoreboard.matchups:
        team_ids = [t.team_id for t in matchup.teams]
        if team_id not in team_ids:
            continue
        team = next(t for t in matchup.teams if t.team_id == team_id)
        opponent = next(t for t in matchup.teams if t.team_id != team_id)
        return Matchup(
            platform="yahoo",
            week=week,
            team_name=team.name,
            opponent_name=opponent.name,
            team_projected=getattr(team, "team_projected_points", None),
            opponent_projected=getattr(opponent, "team_projected_points", None),
        )
    raise ValueError(f"No Yahoo matchup found for team {team_id} in week {week}")


def get_free_agents(config: dict, size: int = 50) -> list[FreeAgent]:
    query = get_query(config)
    players = query.get_league_players(player_count_limit=size, is_only_available_players=True)
    return [
        FreeAgent(
            platform="yahoo",
            player_id=str(p.player_id),
            name=p.name.full,
            position=p.display_position,
            nfl_team=(p.editorial_team_abbr or "").upper(),
            percent_owned=getattr(p, "percent_owned", None),
        )
        for p in players
    ]
