"""ESPN Fantasy Football client, wrapping espn_api into the common data model.

Every function takes a single `league_cfg` entry (one item from config's
`espn:` list, e.g. {"league_id": ..., "team_id": ...}) plus `season`, so a
caller can run this against as many ESPN leagues as they're in.
"""

import os

from espn_api.football import League

from fantasy_agent.platforms.base import FreeAgent, Matchup, Player, Roster


def _get_league(season: int, league_cfg: dict) -> League:
    return League(
        league_id=int(league_cfg["league_id"]),
        year=int(season),
        espn_s2=os.environ.get("ESPN_S2") or None,
        swid=os.environ.get("ESPN_SWID") or None,
    )


def _find_team(league: League, team_id: int):
    for team in league.teams:
        if team.team_id == team_id:
            return team
    raise ValueError(f"ESPN team_id {team_id} not found in league {league.league_id}")


def _to_player(p) -> Player:
    return Player(
        platform="espn",
        player_id=str(p.playerId),
        name=p.name,
        position=p.position,
        nfl_team=p.proTeam,
        lineup_slot=p.lineupSlot,
        status=getattr(p, "injuryStatus", "ACTIVE") or "ACTIVE",
        native_projection=getattr(p, "projected_points", None),
        eligible_slots=list(getattr(p, "eligibleSlots", []) or []),
    )


def get_roster(season: int, league_cfg: dict, week: int) -> Roster:
    league = _get_league(season, league_cfg)
    team = _find_team(league, int(league_cfg["team_id"]))
    players = [_to_player(p) for p in team.roster]
    return Roster(platform="espn", team_name=team.team_name, week=week, players=players)


def get_matchup(season: int, league_cfg: dict, week: int) -> Matchup:
    league = _get_league(season, league_cfg)
    team = _find_team(league, int(league_cfg["team_id"]))
    box_scores = league.box_scores(week)
    for box in box_scores:
        if box.home_team.team_id == team.team_id:
            return Matchup(
                platform="espn",
                week=week,
                team_name=team.team_name,
                opponent_name=box.away_team.team_name,
                team_projected=box.home_projected,
                opponent_projected=box.away_projected,
            )
        if box.away_team.team_id == team.team_id:
            return Matchup(
                platform="espn",
                week=week,
                team_name=team.team_name,
                opponent_name=box.home_team.team_name,
                team_projected=box.away_projected,
                opponent_projected=box.home_projected,
            )
    raise ValueError(f"No ESPN matchup found for team {team.team_name} in week {week}")


def get_free_agents(season: int, league_cfg: dict, size: int = 50) -> list[FreeAgent]:
    league = _get_league(season, league_cfg)
    agents = league.free_agents(size=size)
    return [
        FreeAgent(
            platform="espn",
            player_id=str(a.playerId),
            name=a.name,
            position=a.position,
            nfl_team=a.proTeam,
            percent_owned=getattr(a, "percent_owned", None),
            native_projection=getattr(a, "projected_points", None),
        )
        for a in agents
    ]
