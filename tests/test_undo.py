from __future__ import annotations

import pytest

from engine.actions import CancelTurn, EndTurn, IllegalAction, PlayCard, Undo, apply_action
from engine.history import copy_state
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, catalog_with, make_game, set_hand, spell_def


def _play(state: GameState, seat: int, uid: str) -> GameState:
    return apply_action(state, catalog(), PlayCard(seat, uid))[0]


def test_undo_takes_back_last_card() -> None:
    state = make_game()
    seat = state.current
    a, b, *_ = set_hand(state, seat, ["MAG-S001", "MAG-S012"] + ["MAG-S001"] * 5)
    state = _play(state, seat, a.uid)
    state = _play(state, seat, b.uid)  # unit goes to tier 1
    state, events = apply_action(state, catalog(), Undo(seat))
    p = state.players[seat]
    assert p.inf == 1
    assert p.hand.find(b.uid) is not None
    assert p.tiers[1].cards() == []
    assert [x.def_id for x in p.played_this_turn] == ["MAG-S001"]
    assert events[0].key == "log.undo" and events[0].params["card"] == "MAG-S012"


def test_undo_step_by_step_back_to_start() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    for card in cards[:3]:
        state = _play(state, seat, card.uid)
    for expected_inf in (2, 1, 0):
        state, _ = apply_action(state, catalog(), Undo(seat))
        assert state.players[seat].inf == expected_inf
    assert len(state.players[seat].hand) == 7
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Undo(seat))
    assert exc.value.key == "error.nothing_to_undo"


def test_cancel_turn_restores_turn_start() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 3 + ["MAG-S012"] * 2 + ["MAG-S001"] * 2)
    start_hand = [c.uid for c in state.players[seat].hand]
    for card in cards[:5]:
        state = _play(state, seat, card.uid)
    state, events = apply_action(state, catalog(), CancelTurn(seat))
    p = state.players[seat]
    assert [c.uid for c in p.hand] == start_hand
    assert p.inf == 0 and p.in_play.is_empty() and p.tiers[1].cards() == []
    assert p.resource == 3  # start-of-turn mana stays: SOT happened before the checkpoint
    assert state.undo_stack == []
    assert events[0].params["count"] == 5


def test_end_turn_cannot_be_undone() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    state = _play(state, seat, cards[0].uid)
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.undo_stack == []
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Undo(seat))
    assert exc.value.key == "error.not_your_turn"
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), CancelTurn(state.current))
    assert exc.value.key == "error.nothing_to_undo"


def test_drawing_a_card_creates_a_checkpoint() -> None:
    cat = catalog_with(spell_def("TST-001", [{"do": "draw", "count": 1}]))
    state = make_game()
    seat = state.current
    coin, draw, *_ = set_hand(state, seat, ["MAG-S001", "TST-001"] + ["MAG-S001"] * 5)
    state, _ = apply_action(state, cat, PlayCard(seat, coin.uid))
    state, _ = apply_action(state, cat, PlayCard(seat, draw.uid))
    assert state.undo_stack == []  # the drawn card was seen: no undo past this point
    with pytest.raises(IllegalAction):
        apply_action(state, cat, Undo(seat))


def test_only_current_player_can_undo() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    state = _play(state, seat, cards[0].uid)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Undo((seat + 1) % 2))
    assert exc.value.key == "error.not_your_turn"


def test_view_exposes_undo_availability() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    assert build_view(state, catalog(), seat)["legal"]["can_undo"] is False
    state = _play(state, seat, cards[0].uid)
    legal = build_view(state, catalog(), seat)["legal"]
    assert legal["can_undo"] is True and legal["undo_card"] == "MAG-S001" and legal["undo_count"] == 1
    assert build_view(state, catalog(), (seat + 1) % 2)["legal"]["can_undo"] is False


def test_snapshots_are_shared_not_copied() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001"] * 7)
    state = _play(state, seat, cards[0].uid)
    copied = copy_state(state)
    assert copied.undo_stack[0].state is state.undo_stack[0].state
    assert copied.undo_stack[0].state.undo_stack == []
