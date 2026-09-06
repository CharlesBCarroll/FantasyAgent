from fantasy_agent.engine.trade import find_trade_proposals


def strength(**position_players):
    """Build a strength dict from {position: [(projection, name), ...]} without going through analyze_team."""
    from fantasy_agent.engine.trade import STARTER_SLOTS_BY_POSITION, ROSTER_WORTHY_FLOOR

    result = {}
    for position, players in position_players.items():
        players = sorted(players, reverse=True)
        n = STARTER_SLOTS_BY_POSITION.get(position, 1)
        result[position] = {
            "starters_value": sum(v for v, _ in players[:n]),
            "depth_count": sum(1 for v, _ in players if v >= ROSTER_WORTHY_FLOOR),
            "players": players,
        }
    return result


def test_finds_trade_that_fills_mutual_need():
    # User is weak at QB (only one mediocre QB), has RB surplus (4 good RBs).
    user = strength(
        QB=[(12.0, "Weak QB")],
        RB=[(20.0, "Star RB"), (18.0, "RB2"), (10.0, "RB3"), (8.0, "RB4")],
    )
    # Other team has a strong backup QB to spare and thin RB room.
    other = strength(
        QB=[(25.0, "Star QB"), (20.0, "Backup QB")],
        RB=[(9.0, "Their RB1")],
    )
    proposals = find_trade_proposals(user, {"Rival Team": other})
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["team_name"] == "Rival Team"
    assert proposal["get_position"] == "QB"
    assert proposal["get_player"] == "Backup QB"
    assert proposal["give_position"] == "RB"
    assert proposal["give_player"] in {"RB3", "RB4"}  # spare depth, not a starter


def test_no_proposal_when_no_surplus():
    user = strength(QB=[(12.0, "Weak QB")], RB=[(15.0, "Only RB")])
    other = strength(QB=[(25.0, "Star QB"), (20.0, "Backup QB")], RB=[(9.0, "Their RB1")])
    proposals = find_trade_proposals(user, {"Rival Team": other})
    assert proposals == []


def test_picks_fair_value_pairing_not_just_best_available_on_each_side():
    # Our spare RBs are worth 10 and 6. Their spare QBs are worth 20 and 9.
    # The best FAIR match is our 10 for their 9, not our 10 for their 20.
    user = strength(
        QB=[(12.0, "Weak QB")],
        RB=[(20.0, "Star RB"), (18.0, "RB2"), (10.0, "RB3"), (6.0, "RB4")],
    )
    other = strength(
        QB=[(25.0, "Star QB"), (20.0, "Backup QB"), (9.0, "Third QB")],
        RB=[(9.0, "Their RB1")],
    )
    proposals = find_trade_proposals(user, {"Rival Team": other})
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["give_player"] == "RB3"
    assert proposal["get_player"] == "Third QB"


def test_no_proposal_when_other_team_not_actually_strong_at_weak_position():
    user = strength(
        QB=[(12.0, "Weak QB")],
        RB=[(20.0, "Star RB"), (18.0, "RB2"), (10.0, "RB3"), (8.0, "RB4")],
    )
    # Other team is equally weak at QB — no real surplus to trade for.
    other = strength(QB=[(11.0, "Also Weak QB")], RB=[(9.0, "Their RB1")])
    proposals = find_trade_proposals(user, {"Rival Team": other})
    assert proposals == []
