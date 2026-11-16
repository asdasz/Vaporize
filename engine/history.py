"""Undo support: state snapshots for the current turn."""

from __future__ import annotations

import copy
from typing import Any

from engine.events import Event
from engine.state import GameState

# Events that reveal hidden information. Undoing past them would let a player peek
# (e.g. draw a card, see it, undo), so they become a new checkpoint instead.
REVEALING_EVENTS = frozenset({"log.cards_drawn", "log.deck_reshuffled"})


def copy_state(state: GameState) -> GameState:
    """Deep copy that shares the (immutable) snapshots in the undo stack instead of copying them."""
    memo: dict[int, Any] = {id(entry.state): entry.state for entry in state.undo_stack}
    return copy.deepcopy(state, memo)


def snapshot(state: GameState) -> GameState:
    """Deep copy without the undo stack (snapshots never contain other snapshots)."""
    memo: dict[int, Any] = {id(state.undo_stack): []}
    return copy.deepcopy(state, memo)


def reveals_information(events: list[Event]) -> bool:
    return any(e.key in REVEALING_EVENTS for e in events)
