from __future__ import annotations

from engine.actions import EndTurn, PlayCard, apply_action
from engine.cards import CardInstance
from tests.helpers import catalog, make_game, set_hand


def test_end_turn_discards_played_cards_and_draws_to_seven() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    for card in cards[:5]:
        state, _ = apply_action(state, catalog(), PlayCard(seat, card.uid))
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    p = state.players[seat]
    assert len(p.hand) == 7
    assert p.in_play.is_empty()
    assert p.inf == 0
    # No card is lost: 7 in hand, the remaining 5 split between deck and discard.
    assert len(p.deck) + len(p.discard) == 5


def test_turn_order_and_rounds() -> None:
    state = make_game(players=3)
    first = state.first_player
    seen = []
    for _ in range(4):
        seen.append(state.current)
        state, _ = apply_action(state, catalog(), EndTurn(state.current))
    assert seen == [first, (first + 1) % 3, (first + 2) % 3, first]
    assert state.round == 2


def test_mage_gains_mana_at_start_and_loses_at_end() -> None:
    state = make_game()
    seat = state.current
    assert state.players[seat].resource == 3
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].resource == 0


def test_mana_gain_from_passive_respects_limit() -> None:
    state = make_game()
    seat = state.current
    state.players[seat].resource = 7
    state, _ = apply_action(state, catalog(), EndTurn(seat))  # eot: 7 -> 4
    assert state.players[seat].resource == 4
    other = state.current
    state, _ = apply_action(state, catalog(), EndTurn(other))
    # Back to seat: sot +3, capped at limit 4.
    assert state.players[seat].resource == 4


def test_units_score_vp_at_end_of_turn() -> None:
    state = make_game()
    seat = state.current
    p = state.players[seat]
    p.tiers[2].place(CardInstance(uid="x1", def_id="MAG-S012", owner=seat))
    p.tiers[3].place(CardInstance(uid="x2", def_id="MAG-S012", owner=seat))
    state.tier4.place(CardInstance(uid="x3", def_id="MAG-S012", owner=seat))
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 1 + 2 + 3


def test_game_ends_after_round_when_goal_reached() -> None:
    state = make_game(players=2)
    first = state.first_player
    state.players[first].vp = 30
    state, _ = apply_action(state, catalog(), EndTurn(first))
    assert state.phase == "actions"  # second player still gets a turn
    state.players[state.current].vp = 31
    state, events = apply_action(state, catalog(), EndTurn(state.current))
    assert state.phase == "game_over"
    assert state.winners == [(first + 1) % 2]
    assert events[-1].key == "log.game_over"


def test_tie_broken_by_highest_tier() -> None:
    state = make_game(players=2)
    first, second = state.first_player, (state.first_player + 1) % 2
    state.players[first].vp = 30
    state.players[second].vp = 30
    state.players[second].tiers[2].place(CardInstance(uid="t", def_id="MAG-S012", owner=second))
    state.players[second].vp -= 1  # tier 2 unit scores 1 VP at end of their turn
    state, _ = apply_action(state, catalog(), EndTurn(first))
    state, _ = apply_action(state, catalog(), EndTurn(second))
    assert state.winners == [second]
