"""Player actions. `apply_action` validates an action and returns a new state + events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.context import EffectContext
from engine.events import Event
from engine.history import copy_state, reveals_information, snapshot
from engine.resolver import resolve_effects
from engine.rules import MIN_HAND
from engine.state import GameState, PlayedCard, UndoEntry
from engine.turn import end_turn


@dataclass(frozen=True)
class PlayCard:
    seat: int
    card_uid: str


@dataclass(frozen=True)
class EndTurn:
    seat: int


@dataclass(frozen=True)
class Undo:
    """Take back the last card played this turn."""

    seat: int


@dataclass(frozen=True)
class CancelTurn:
    """Take back everything done this turn (back to the last checkpoint)."""

    seat: int


Action = Union[PlayCard, EndTurn, Undo, CancelTurn]


class IllegalAction(Exception):
    """Raised for an action the rules don't allow. Carries a translation key."""

    def __init__(self, key: str, **params: Any) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


def _check_turn(state: GameState, seat: int) -> None:
    if state.phase != "actions":
        raise IllegalAction("error.game_over")
    if seat != state.current:
        raise IllegalAction("error.not_your_turn")


def check_play(state: GameState, catalog: Catalog, seat: int, card_uid: str) -> CardInstance:
    _check_turn(state, seat)
    player = state.players[seat]
    card = player.hand.find(card_uid)
    if card is None:
        raise IllegalAction("error.card_not_in_hand")
    if len(player.hand) <= MIN_HAND:
        raise IllegalAction("error.min_hand", min=MIN_HAND)
    if catalog.card(card.def_id).is_unit and not player.tiers[1].has_free():
        raise IllegalAction("error.tier_full", tier=1)
    return card


def legal_plays(state: GameState, catalog: Catalog, seat: int) -> list[str]:
    legal = []
    for card in state.players[seat].hand:
        try:
            check_play(state, catalog, seat, card.uid)
        except IllegalAction:
            continue
        legal.append(card.uid)
    return legal


def _play_card(state: GameState, catalog: Catalog, action: PlayCard, events: list[Event]) -> None:
    check_play(state, catalog, action.seat, action.card_uid)
    player = state.players[action.seat]
    card = player.hand.take(action.card_uid)
    cdef = catalog.card(card.def_id)
    player.played_this_turn.append(PlayedCard(card.uid, cdef.id, cdef.elements))
    if cdef.is_unit:
        player.tiers[1].place(card)
        card.fixed_attack = cdef.attack
        card.fixed_health = cdef.health
        card.current_hp = cdef.health
        events.append(Event("log.unit_played", {"seat": action.seat, "card": cdef.id, "tier": 1}))
    else:
        player.in_play.put_bottom(card)
        events.append(Event("log.card_played", {"seat": action.seat, "card": cdef.id}))
    resolve_effects(EffectContext(state, catalog, action.seat, card, events), cdef.effects)


def _undo(state: GameState, action: Undo, events: list[Event]) -> GameState:
    _check_turn(state, action.seat)
    if not state.undo_stack:
        raise IllegalAction("error.nothing_to_undo")
    entry = state.undo_stack[-1]
    new_state = copy_state(entry.state)
    new_state.undo_stack = list(state.undo_stack[:-1])
    events.append(Event("log.undo", {"seat": action.seat, "card": entry.card_id}))
    return new_state


def _cancel_turn(state: GameState, action: CancelTurn, events: list[Event]) -> GameState:
    _check_turn(state, action.seat)
    if not state.undo_stack:
        raise IllegalAction("error.nothing_to_undo")
    new_state = copy_state(state.undo_stack[0].state)
    new_state.undo_stack = []
    events.append(Event("log.turn_cancelled", {"seat": action.seat, "count": len(state.undo_stack)}))
    return new_state


def apply_action(state: GameState, catalog: Catalog, action: Action) -> tuple[GameState, list[Event]]:
    """Validate and apply an action. The input state is never modified."""
    events: list[Event] = []
    if isinstance(action, Undo):
        return _undo(state, action, events), events
    if isinstance(action, CancelTurn):
        return _cancel_turn(state, action, events), events

    new_state = copy_state(state)
    if isinstance(action, PlayCard):
        before = snapshot(state)
        _play_card(new_state, catalog, action, events)
        if reveals_information(events):
            new_state.undo_stack = []  # new checkpoint: can't undo past revealed information
        else:
            card = state.players[action.seat].hand.find(action.card_uid)
            card_id = card.def_id if card else ""
            new_state.undo_stack.append(UndoEntry(before, card_id))
    elif isinstance(action, EndTurn):
        _check_turn(new_state, action.seat)
        new_state.undo_stack = []  # ending the turn commits it; nothing can be undone after this
        end_turn(new_state, catalog, events)
    else:
        raise IllegalAction("error.unknown_action")
    return new_state, events
