from __future__ import annotations

import pytest

from engine.actions import Buy, IllegalAction, Refresh, Undo, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_cards, make_game


def _shared(state: GameState, ids: list[str], deck: list[str] | None = None) -> None:
    m = state.shared_market
    cards = make_cards(state, -1, ids)
    m.row.slots = list(cards) + [None] * (6 - len(cards))
    m.deck.cards = make_cards(state, -1, deck or [])


def test_private_market_starts_with_3_of_15() -> None:
    state = make_game()
    for p in state.players:
        assert len(p.private_market.row.cards()) == 3 and len(p.private_market.deck) == 12


def test_buy_private_card_goes_to_discard_and_reveals_new() -> None:
    state = make_game()
    seat = state.current
    p = state.players[seat]
    card = p.private_market.row.slots[1]
    cost = catalog().card(card.def_id).cost
    p.inf = cost
    state, events = apply_action(state, catalog(), Buy(seat, "private", 1))
    p = state.players[seat]
    assert p.inf == 0 and p.discard.find(card.uid) and p.private_market.row.slots[1] is not None
    assert len(p.private_market.deck) == 11
    assert state.undo_stack == []  # a new card was revealed: can't undo
    assert [e.key for e in events][-1] == "log.market_revealed"


def test_buy_needs_enough_inf() -> None:
    state = make_game()
    seat = state.current
    state.players[seat].inf = 0
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Buy(seat, "private", 0))
    assert exc.value.key == "error.not_enough_inf"


def test_shared_market_prices_plus_one_left_minus_one_right() -> None:
    state = make_game()
    seat = state.current
    _shared(state, ["MAG-P031"] * 6)  # printed cost 3
    state.players[seat].inf = 2
    view = build_view(state, catalog(), seat)
    assert [e["price"] for e in view["shared_market"]["row"]] == [4, 3, 3, 3, 3, 2]
    assert view["legal"]["market"]["shared_buy"] == [5]
    state, _ = apply_action(state, catalog(), Buy(seat, "shared", 5))
    assert state.players[seat].inf == 0


def test_refresh_shared_free_once_then_costs_1() -> None:
    state = make_game()
    seat = state.current
    _shared(state, ["MAG-P031", "MAG-P032", "MAG-P033", "MAG-P034", "MAG-P035", "MAG-P036"], deck=["MAG-P037", "MAG-P038"])
    state.players[seat].inf = 1
    rightmost = state.shared_market.row.slots[5].uid
    state, _ = apply_action(state, catalog(), Refresh(seat, "shared"))
    m = state.shared_market
    assert state.players[seat].inf == 1 and m.removed.find(rightmost)
    assert [catalog().card(c.def_id).number for c in m.row.slots] == [37, 31, 32, 33, 34, 35]
    state, _ = apply_action(state, catalog(), Refresh(seat, "shared"))
    assert state.players[seat].inf == 0
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Refresh(seat, "shared"))


def test_market_deck_reshuffles_removed_cards_when_empty() -> None:
    state = make_game()
    seat = state.current
    _shared(state, ["MAG-P031"] * 6)
    state.shared_market.removed.cards = make_cards(state, -1, ["MAG-P040"])
    state, events = apply_action(state, catalog(), Refresh(seat, "shared"))
    m = state.shared_market
    assert catalog().card(m.row.slots[0].def_id).number == 40 or catalog().card(m.row.slots[0].def_id).number == 31
    assert any(e.key == "log.market_reshuffled" for e in events)


def test_private_refresh_costs_1() -> None:
    state = make_game()
    seat = state.current
    state.players[seat].inf = 1
    state, _ = apply_action(state, catalog(), Refresh(seat, "private"))
    assert state.players[seat].inf == 0
    assert len(state.players[seat].private_market.removed) == 1


def test_unknown_market_rejected() -> None:
    state = make_game()
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Buy(state.current, "black", 0))
    assert exc.value.key == "error.unknown_market"
