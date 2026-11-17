"""Player actions. `apply_action` validates an action and returns a new state + events.

The input state is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.context import EffectContext
from engine.development import check_develop, develop_unit
from engine.errors import IllegalAction
from engine.events import Event
from engine.history import copy_state, reveals_information, snapshot
from engine.prompts import NeedChoice, PendingChoice
from engine.resolver import resolve_effects
from engine.rules import MIN_HAND
from engine.state import GameState, PlayedCard, UndoEntry
from engine.turn import end_turn

__all__ = [
    "Action", "CancelChoice", "CancelTurn", "Develop", "EndTurn", "IllegalAction", "PlayCard", "Respond", "Undo",
    "apply_action", "check_play", "legal_plays",
]


@dataclass(frozen=True)
class PlayCard:
    seat: int
    card_uid: str


@dataclass(frozen=True)
class Respond:
    """Answer the pending prompt (see engine/prompts.py)."""

    seat: int
    answer: Any


@dataclass(frozen=True)
class CancelChoice:
    """Stop playing the card that is waiting for a choice; it goes back to the hand."""

    seat: int


@dataclass(frozen=True)
class Develop:
    """Pay inf to move one of your units up one tier."""

    seat: int
    unit_uid: str


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


Action = Union[PlayCard, Respond, CancelChoice, Develop, EndTurn, Undo, CancelTurn]


def _check_turn(state: GameState, seat: int) -> None:
    if state.phase != "actions":
        raise IllegalAction("error.game_over")
    if seat != state.current:
        raise IllegalAction("error.not_your_turn")


def check_play(state: GameState, catalog: Catalog, seat: int, card_uid: str) -> CardInstance:
    _check_turn(state, seat)
    if state.pending is not None:
        raise IllegalAction("error.choice_pending")
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


def _play_card(
    state: GameState, catalog: Catalog, seat: int, card_uid: str, answers: list[Any], events: list[Event]
) -> None:
    check_play(state, catalog, seat, card_uid)
    player = state.players[seat]
    card = player.hand.take(card_uid)
    cdef = catalog.card(card.def_id)
    player.played_this_turn.append(PlayedCard(card.uid, cdef.id, cdef.elements))
    if cdef.is_unit:
        player.tiers[1].place(card)
        card.fixed_attack = cdef.attack
        card.fixed_health = cdef.health
        card.current_hp = cdef.health
        events.append(Event("log.unit_played", {"seat": seat, "card": cdef.id, "tier": 1}))
    else:
        player.in_play.put_bottom(card)
        events.append(Event("log.card_played", {"seat": seat, "card": cdef.id}))
    resolve_effects(EffectContext(state, catalog, seat, card, events, answers=answers), cdef.effects)


def _resolve_play(
    base: GameState, catalog: Catalog, seat: int, card_uid: str, answers: list[Any]
) -> tuple[GameState, list[Event]]:
    """Play a card from `base` (no pending choice) with the answers given so far.

    Either the card resolves completely, or the result is `base` plus a pending prompt.
    """
    new_state = copy_state(base)
    events: list[Event] = []
    try:
        _play_card(new_state, catalog, seat, card_uid, answers, events)
    except NeedChoice as need:
        waiting = copy_state(base)
        waiting.pending = PendingChoice(seat, card_uid, list(answers), need.prompt)
        return waiting, []
    if reveals_information(events):
        new_state.undo_stack = []  # new checkpoint: can't undo past revealed information
    else:
        card = base.players[seat].hand.find(card_uid)
        new_state.undo_stack.append(UndoEntry(snapshot(base), card.def_id if card else ""))
    return new_state, events


def _respond(state: GameState, catalog: Catalog, action: Respond) -> tuple[GameState, list[Event]]:
    _check_turn(state, action.seat)
    pending = state.pending
    if pending is None:
        raise IllegalAction("error.no_choice_pending")
    base = copy_state(state)
    base.pending = None
    return _resolve_play(base, catalog, pending.seat, pending.card_uid, [*pending.answers, action.answer])


def _cancel_choice(state: GameState, action: CancelChoice) -> tuple[GameState, list[Event]]:
    _check_turn(state, action.seat)
    pending = state.pending
    if pending is None:
        raise IllegalAction("error.no_choice_pending")
    if not pending.prompt.cancellable:
        raise IllegalAction("error.choice_not_cancellable")
    new_state = copy_state(state)
    new_state.pending = None
    card = state.players[pending.seat].hand.find(pending.card_uid)
    return new_state, [Event("log.play_cancelled", {"seat": pending.seat, "card": card.def_id if card else ""})]


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
    if isinstance(action, Respond):
        return _respond(state, catalog, action)
    if isinstance(action, CancelChoice):
        return _cancel_choice(state, action)
    if state.pending is not None:
        _check_turn(state, action.seat)
        raise IllegalAction("error.choice_pending")
    if isinstance(action, Undo):
        return _undo(state, action, events), events
    if isinstance(action, CancelTurn):
        return _cancel_turn(state, action, events), events
    if isinstance(action, PlayCard):
        return _resolve_play(state, catalog, action.seat, action.card_uid, [])
    if isinstance(action, Develop):
        _check_turn(state, action.seat)
        option = check_develop(state, catalog, action.seat, action.unit_uid)
        new_state = copy_state(state)
        develop_unit(new_state, catalog, action.seat, option, events)
        unit = next(u for _, u in state.units_of(action.seat) if u.uid == action.unit_uid)
        new_state.undo_stack.append(UndoEntry(snapshot(state), unit.def_id))
        return new_state, events
    if isinstance(action, EndTurn):
        _check_turn(state, action.seat)
        new_state = copy_state(state)
        new_state.undo_stack = []  # ending the turn commits it; nothing can be undone after this
        end_turn(new_state, catalog, events)
        return new_state, events
    raise IllegalAction("error.unknown_action")
