"""Drawing cards, with the empty-deck reshuffle rule."""

from __future__ import annotations

from engine.events import Event
from engine.state import GameState


def reshuffle_discard(state: GameState, seat: int, events: list[Event]) -> bool:
    """Shuffle the discard pile into a new deck. Returns False if there was nothing to shuffle."""
    player = state.players[seat]
    if player.discard.is_empty():
        return False
    player.deck.cards = player.discard.take_all()
    player.deck.shuffle(state.rng)
    events.append(Event("log.deck_reshuffled", {"seat": seat, "count": len(player.deck)}))
    return True


def draw_cards(state: GameState, seat: int, count: int, events: list[Event]) -> int:
    """Draw up to `count` cards one at a time. Returns how many were drawn.

    When the deck is empty, the discard pile is shuffled into a new deck.
    When both are empty, drawing stops and the player keeps a smaller hand.
    """
    player = state.players[seat]
    drawn = 0
    for _ in range(count):
        if player.deck.is_empty() and not reshuffle_discard(state, seat, events):
            events.append(Event("log.draw_exhausted", {"seat": seat}))
            break
        player.hand.put_bottom(player.deck.draw())
        drawn += 1
    if drawn:
        events.append(Event("log.cards_drawn", {"seat": seat, "count": drawn}))
    return drawn


def draw_up_to(state: GameState, seat: int, hand_size: int, events: list[Event]) -> int:
    missing = hand_size - len(state.players[seat].hand)
    return draw_cards(state, seat, missing, events) if missing > 0 else 0
