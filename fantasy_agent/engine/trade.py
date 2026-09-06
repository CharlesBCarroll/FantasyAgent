"""Trade analyzer: finds mutually plausible trades from positional strength.

Every team's "starters value" and "depth" per position is computed from the
same blended projections used everywhere else in the pipeline (project_player),
so this reuses the existing self-learning-tuned signal rather than inventing
a separate trade-value model. A team is "weak" at a position if its starters
value is below the league average; "surplus" if it has more roster-worthy
depth than its typical starter count requires.

STARTER_SLOTS_BY_POSITION is a simplifying assumption (standard-ish lineup
requirements), not read from each league's actual roster settings — good
enough for a heuristic, not a guarantee of your league's exact format.
"""

from collections import defaultdict

from fantasy_agent.engine.recommend import project_player
from fantasy_agent.platforms.base import Roster

STARTER_SLOTS_BY_POSITION = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "D/ST": 1}
ROSTER_WORTHY_FLOOR = 5.0
SURPLUS_DEPTH_MARGIN = 2


def analyze_team(
    roster: Roster,
    season: int,
    week: int,
    weights: dict[tuple[str, str], float] | None = None,
    scoring: str | dict | None = None,
) -> dict:
    """{position: {"starters_value": float, "depth_count": int, "players": [(projection, name), ...] desc}}"""
    by_position = defaultdict(list)
    for player in roster.players:
        blended, _ = project_player(player, season, week, weights, scoring)
        if blended is None:
            continue
        by_position[player.position].append((blended, player.name))

    strength = {}
    for position, values in by_position.items():
        values.sort(reverse=True)
        starter_slots = STARTER_SLOTS_BY_POSITION.get(position, 1)
        strength[position] = {
            "starters_value": sum(v for v, _ in values[:starter_slots]),
            "depth_count": sum(1 for v, _ in values if v >= ROSTER_WORTHY_FLOOR),
            "players": values,
        }
    return strength


def _league_average_starters_value(all_strengths: list[dict]) -> dict[str, float]:
    totals = defaultdict(list)
    for strength in all_strengths:
        for position, info in strength.items():
            totals[position].append(info["starters_value"])
    return {position: sum(vals) / len(vals) for position, vals in totals.items()}


def find_trade_proposals(
    user_strength: dict,
    other_teams: dict[str, dict],
    max_proposals: int = 3,
) -> list[dict]:
    """Propose trades: give from where you have real bench depth, get help where you're weak.

    `other_teams` is {team_name: strength_dict} for every other team in the
    league, as returned by analyze_team.
    """
    league_avg = _league_average_starters_value([user_strength, *other_teams.values()])
    if not league_avg:
        return []

    gaps = {
        position: user_strength.get(position, {"starters_value": 0.0})["starters_value"] - avg
        for position, avg in league_avg.items()
    }
    weak_position = min(gaps, key=gaps.get)

    surplus_positions = [
        position
        for position, info in user_strength.items()
        if info["depth_count"] >= STARTER_SLOTS_BY_POSITION.get(position, 1) + SURPLUS_DEPTH_MARGIN
        and gaps.get(position, 0) > 0
    ]
    if not surplus_positions:
        return []
    surplus_position = max(surplus_positions, key=lambda p: gaps[p])

    starter_slots_weak = STARTER_SLOTS_BY_POSITION.get(weak_position, 1)
    starter_slots_surplus = STARTER_SLOTS_BY_POSITION.get(surplus_position, 1)

    our_spare_players = user_strength.get(surplus_position, {}).get("players", [])[starter_slots_surplus:]
    if not our_spare_players:
        return []

    proposals = []
    for team_name, strength in other_teams.items():
        their_weak_avg = league_avg.get(weak_position, 0.0)
        their_surplus_avg = league_avg.get(surplus_position, 0.0)
        their_strength_at_weak = strength.get(weak_position, {"starters_value": 0.0})["starters_value"]
        their_gap_at_surplus = strength.get(surplus_position, {"starters_value": 0.0})["starters_value"] - their_surplus_avg

        if their_strength_at_weak <= their_weak_avg:
            continue  # they aren't actually strong where we're weak
        if their_gap_at_surplus >= 0:
            continue  # they aren't actually weak where we have surplus

        their_depth_beyond_starters = strength.get(weak_position, {}).get("players", [])[starter_slots_weak:]
        if not their_depth_beyond_starters:
            continue

        # Pick whichever (give, get) pairing across both sides' available
        # pieces has the closest value match — favors fair, plausible-to-
        # accept trades over just offering our single best spare piece.
        (give_value, give_name), (get_value, get_name) = min(
            ((give, get) for give in our_spare_players for get in their_depth_beyond_starters),
            key=lambda pair: abs(pair[0][0] - pair[1][0]),
        )

        proposals.append(
            {
                "team_name": team_name,
                "give_position": surplus_position,
                "give_player": give_name,
                "give_value": give_value,
                "get_position": weak_position,
                "get_player": get_name,
                "get_value": get_value,
                "value_delta": get_value - give_value,
            }
        )

    proposals.sort(key=lambda p: p["value_delta"], reverse=True)
    return proposals[:max_proposals]
