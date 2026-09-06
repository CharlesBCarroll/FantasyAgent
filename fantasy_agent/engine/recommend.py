"""Start/sit and waiver-wire recommendation logic.

Works entirely off blended projections (engine/blend.py) plus lineup-eligibility
metadata already present on each Player/FreeAgent. This module does not do any
web research itself — it produces the structured signals (swap suggestions,
status alerts, close calls, waiver candidates) that the runtime research layer
(the scheduled Claude agent) uses to decide what to actually go dig up news on.
"""

from fantasy_agent.engine.blend import blend, matchup_adjustment
from fantasy_agent.platforms.base import FreeAgent, Player, Roster
from fantasy_agent.projections import nfl_data_source, sleeper_source, weather_source
from fantasy_agent.utils import normalize_name, normalize_team_abbr

STATUS_ALERT_LEVELS = {"QUESTIONABLE", "DOUBTFUL", "OUT", "IR"}
SEVERE_STATUS_LEVELS = {"OUT", "DOUBTFUL"}
CLOSE_CALL_MARGIN = 2.0


def _trending_adds() -> dict[str, int]:
    """Sleeper's 24h trending-add counts, keyed by normalized player name.

    Best-effort: Sleeper is a third-party signal, not required for the core
    pipeline, so a network hiccup here shouldn't break recommendations.
    """
    try:
        return sleeper_source.get_trending("add", lookback_hours=24, limit=100)
    except Exception:
        return {}


def _trending_drops() -> dict[str, int]:
    """Sleeper's 24h trending-drop counts, keyed by normalized player name.

    Used as an early warning on your OWN roster — a rostered player being
    cut across the league en masse often precedes an official injury/role
    announcement.
    """
    try:
        return sleeper_source.get_trending("drop", lookback_hours=24, limit=100)
    except Exception:
        return {}


def project_player(
    player: Player | FreeAgent,
    season: int,
    week: int,
    weights: dict[tuple[str, str], float] | None,
    scoring: str | dict | None = None,
) -> tuple[float | None, dict]:
    resolved_scoring = nfl_data_source.resolve_scoring(scoring)
    sources = {
        "native": player.native_projection,
        "trend": nfl_data_source.recent_trend(player.name, season, week, resolved_scoring),
    }
    blended, breakdown = blend(sources, player.position, weights)

    if blended is not None and player.opponent:
        opp_team = normalize_team_abbr(player.opponent.lstrip("@"))
        rank = nfl_data_source.opponent_defense_rank(
            player.position, opp_team, season, week, resolved_scoring
        )
        factor = matchup_adjustment(rank)
        blended = blended * factor
        breakdown["matchup_adjustment_factor"] = factor

    if blended is not None:
        weather = weather_source.get_game_weather(season, week, player.nfl_team)
        weather_factor = weather_source.weather_adjustment(weather, player.position)
        if weather_factor != 1.0:
            blended = blended * weather_factor
            breakdown["weather_adjustment_factor"] = weather_factor

    return blended, breakdown


def _eligible_bench_candidates(roster: Roster, starter: Player) -> list[Player]:
    return [
        p
        for p in roster.bench()
        if starter.lineup_slot in p.eligible_slots or p.position == starter.position
    ]


def generate_lineup_recommendations(
    roster: Roster,
    season: int,
    week: int,
    weights: dict[tuple[str, str], float] | None = None,
    scoring: str | dict | None = None,
) -> dict:
    resolved_scoring = nfl_data_source.resolve_scoring(scoring)
    projections: dict[str, dict] = {}
    for player in roster.players:
        blended, breakdown = project_player(player, season, week, weights, scoring)
        projections[player.player_id] = {
            "name": player.name,
            "position": player.position,
            "lineup_slot": player.lineup_slot,
            "status": player.status,
            "blended_projection": blended,
            "breakdown": breakdown,
            "rest_of_season": nfl_data_source.rest_of_season_matchups(
                player.position, player.nfl_team, season, week, resolved_scoring
            ),
        }

    status_alerts = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "status": p.status,
            "lineup_slot": p.lineup_slot,
        }
        for p in roster.starters()
        if p.status in STATUS_ALERT_LEVELS
    ]

    trending_drops = _trending_drops()
    trending_down_alerts = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "lineup_slot": p.lineup_slot,
            "drop_count": trending_drops[normalize_name(p.name)],
        }
        for p in roster.players
        if normalize_name(p.name) in trending_drops
    ]

    swaps = []
    close_calls = []
    for starter in roster.starters():
        starter_proj = projections[starter.player_id]["blended_projection"]
        candidates = _eligible_bench_candidates(roster, starter)
        for bench_player in candidates:
            bench_proj = projections[bench_player.player_id]["blended_projection"]
            if starter_proj is None or bench_proj is None:
                continue
            margin = bench_proj - starter_proj
            if margin > CLOSE_CALL_MARGIN:
                swaps.append(
                    {
                        "sit": starter.name,
                        "sit_projection": starter_proj,
                        "start": bench_player.name,
                        "start_projection": bench_proj,
                        "slot": starter.lineup_slot,
                        "margin": margin,
                    }
                )
            elif 0 < margin <= CLOSE_CALL_MARGIN:
                close_calls.append(
                    {
                        "slot": starter.lineup_slot,
                        "current_starter": starter.name,
                        "current_starter_projection": starter_proj,
                        "bench_alternative": bench_player.name,
                        "bench_alternative_projection": bench_proj,
                        "margin": margin,
                    }
                )

    return {
        "team_name": roster.team_name,
        "platform": roster.platform,
        "week": week,
        "projections": projections,
        "status_alerts": status_alerts,
        "trending_down_alerts": trending_down_alerts,
        "start_sit_swaps": swaps,
        "close_calls": close_calls,
    }


def generate_waiver_recommendations(
    roster: Roster,
    free_agents: list[FreeAgent],
    season: int,
    week: int,
    weights: dict[tuple[str, str], float] | None = None,
    top_n: int = 3,
    scoring: str | dict | None = None,
) -> dict[str, list[dict]]:
    weakest_by_position: dict[str, float] = {}
    for player in roster.players:
        blended, _ = project_player(player, season, week, weights, scoring)
        if blended is None:
            continue
        current = weakest_by_position.get(player.position)
        if current is None or blended < current:
            weakest_by_position[player.position] = blended

    trending_adds = _trending_adds()

    by_position: dict[str, list[dict]] = {}
    for agent in free_agents:
        blended, breakdown = project_player(agent, season, week, weights, scoring)
        if blended is None:
            continue
        by_position.setdefault(agent.position, []).append(
            {
                "name": agent.name,
                "nfl_team": agent.nfl_team,
                "projection": blended,
                "percent_owned": agent.percent_owned,
                "breakdown": breakdown,
                "beats_weakest_rostered": blended > weakest_by_position.get(agent.position, 0.0),
                "trending_adds": trending_adds.get(normalize_name(agent.name)),
            }
        )

    return {
        position: sorted(candidates, key=lambda c: c["projection"], reverse=True)[:top_n]
        for position, candidates in by_position.items()
    }


def suggest_handcuffs(
    status_alerts: list[dict],
    roster_players: list[Player],
    free_agents: list[FreeAgent],
    season: int,
    week: int,
    weights: dict[tuple[str, str], float] | None = None,
    scoring: str | dict | None = None,
) -> dict[str, dict]:
    """For each OUT/DOUBTFUL status alert, suggest the best same-team/same-position free agent.

    A rostered player's most direct replacement is almost always the backup
    on their own NFL team stepping into the vacated role, so this filters
    free agents to that team+position rather than a generic top-waiver list.
    """
    severe_ids = {a["player_id"] for a in status_alerts if a["status"] in SEVERE_STATUS_LEVELS}
    if not severe_ids:
        return {}

    roster_by_id = {p.player_id: p for p in roster_players}
    trending_adds = _trending_adds()

    suggestions: dict[str, dict] = {}
    for player_id in severe_ids:
        injured = roster_by_id.get(player_id)
        if injured is None:
            continue
        candidates = [
            agent
            for agent in free_agents
            if agent.nfl_team == injured.nfl_team and agent.position == injured.position
        ]
        scored = []
        for agent in candidates:
            blended, _ = project_player(agent, season, week, weights, scoring)
            if blended is None:
                continue
            scored.append((blended, trending_adds.get(normalize_name(agent.name), 0), agent))
        if not scored:
            continue
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        best_projection, _, best_agent = scored[0]
        suggestions[player_id] = {
            "name": best_agent.name,
            "nfl_team": best_agent.nfl_team,
            "projection": best_projection,
            "trending_adds": trending_adds.get(normalize_name(best_agent.name)),
        }

    return suggestions
