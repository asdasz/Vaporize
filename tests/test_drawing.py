from __future__ import annotations

from engine.drawing import draw_cards, draw_up_to
from engine.events import Event
from tests.helpers import make_cards, make_game


def test_starting_hand_is_seven_and_deck_has_rest() -> None:
    state = make_game(players=3)
    for p in state.players:
        assert len(p.hand) == 7
        assert len(p.deck) == 5


def test_draw_reshuffles_discard_when_deck_empty() -> None:
    state = make_game()
    p = state.players[0]
    p.hand.cards, p.deck.cards = [], []
    p.discard.cards = make_cards(state, 0, ["MAG-S01"] * 4)
    events: list[Event] = []
    assert draw_cards(state, 0, 3, events) == 3
    assert len(p.hand) == 3 and len(p.deck) == 1 and p.discard.is_empty()
    assert any(e.key == "log.deck_reshuffled" for e in events)


def test_draw_continues_from_reshuffled_discard_midway() -> None:
    state = make_game()
    p = state.players[0]
    p.hand.cards = []
    p.deck.cards = make_cards(state, 0, ["MAG-S01"] * 2)
    p.discard.cards = make_cards(state, 0, ["MAG-S02"] * 5)
    draw_up_to(state, 0, 7, [])
    assert len(p.hand) == 7
    assert len(p.deck) == 0


def test_draw_stops_when_deck_and_discard_are_empty() -> None:
    state = make_game()
    p = state.players[0]
    p.hand.cards = []
    p.deck.cards = make_cards(state, 0, ["MAG-S01"] * 2)
    p.discard.cards = make_cards(state, 0, ["MAG-S01"])
    events: list[Event] = []
    assert draw_up_to(state, 0, 7, events) == 3
    assert len(p.hand) == 3
    assert any(e.key == "log.draw_exhausted" for e in events)
