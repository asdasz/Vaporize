"""Player actions. `apply_action` validates an action and returns a new state + events.

The input state is never modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.attacks import attack
from engine.bank import bank
from engine.context import EffectContext
from engine.development import check_develop, develop_unit
from engine.element_swap import check_swap, swapped_elements
from engine.effects.registry import get_effect
from engine.errors import IllegalAction
from engine.events import Event
from engine.history import copy_state, reveals_information, snapshot
from engine.market import MARKETS, buy, refresh
from engine.prompts import NeedChoice, PendingChoice
from engine.removal import remove_card
from engine.playing import resolve_played_card
from engine.rules import MIN_HAND
from engine.conditions import evaluate_condition
from engine.state import GameState, PlayedCard, UndoEntry
from engine.turn import end_turn

__all__ = [
    "Action", "Attack", "Bank", "Buy", "CancelChoice", "CancelTurn", "Develop", "EndTurn", "IllegalAction", "PlayCard",
    "Refresh", "RemoveCard", "Respond", "Undo",
    "apply_action", "check_play", "legal_plays",
]


@dataclass(frozen=True)
class PlayCard:
    seat: int
    card_uid: str
    swap: tuple[str, str] | None = None  # Mage passive: (printed element, new element)


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
    pay: str = "inf"  # inf | resource (units with `develop_with_resource`, e.g. 145)


@dataclass(frozen=True)
class Bank:
    """Move class resource onto (amount > 0) or off (amount < 0) one of your `resource_bank` units (143)."""

    seat: int
    unit_uid: str
    amount: int


@dataclass(frozen=True)
class RemoveCard:
    """Pay the removal cost to remove a card played this turn or in the discard pile from the game."""

    seat: int
    card_uid: str


@dataclass(frozen=True)
class Attack:
    """Attack an enemy unit on the same tier or one tier higher."""

    seat: int
    attacker_uid: str
    target_uid: str


@dataclass(frozen=True)
class Buy:
    """Buy the card in `slot` of the shared market or your private market."""

    seat: int
    market: str  # shared | private | basic
    slot: int
    pay: str = "inf"  # inf | vp (cards with an alternative VP cost)


@dataclass(frozen=True)
class Refresh:
    seat: int
    market: str  # shared | private


@dataclass(frozen=True)
class EndTurn:
    seat: int
    hand_discards: tuple[str, ...] = ()  # hand cards with `hand_eot` the player chooses to discard (e.g. 731)


@dataclass(frozen=True)
class Undo:
    """Take back the last card played this turn."""

    seat: int


@dataclass(frozen=True)
class CancelTurn:
    """Take back everything done this turn (back to the last checkpoint)."""

    seat: int


Action = Union[PlayCard, Respond, CancelChoice, Develop, Bank, RemoveCard, Attack, Buy, Refresh, EndTurn, Undo, CancelTurn]


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
    if card_uid in player.locked_cards:
        raise IllegalAction("error.card_locked")
    cdef = catalog.card(card.def_id)
    if cdef.is_unit and not player.tiers[1].has_free():
        raise IllegalAction("error.tier_full", tier=1)
    if _has_required(cdef.effects) and not _requirements_ok(state, catalog, seat, card):
        raise IllegalAction("error.requirement_not_met")  # a mandatory (negative) part can't happen
    return card


def _has_required(nodes: Any) -> bool:
    for node in nodes:
        if node.get("required"):
            return True
        if "if" in node and (_has_required(node.get("then", [])) or _has_required(node.get("else", []))):
            return True
        if "choose_one" in node and any(_has_required(opt) for opt in node["choose_one"]):
            return True
    return False


def _requirements_ok(state: GameState, catalog: Catalog, seat: int, card: CardInstance) -> bool:
    """Dry run: with the card counted as played, could every mandatory effect on the chosen path happen?"""
    trial = copy_state(state)
    player = trial.players[seat]
    played = player.hand.take(card.uid)
    player.in_play.put_bottom(played)
    player.played_this_turn.append(PlayedCard(played.uid, played.def_id, catalog.card(played.def_id).elements))
    return _nodes_ok(EffectContext(trial, catalog, seat, played, []), catalog.card(card.def_id).effects)


def _nodes_ok(ctx: EffectContext, nodes: Any) -> bool:
    for node in nodes:
        if "if" in node:
            try:
                ok = _nodes_ok(ctx, node.get("then", []) if evaluate_condition(ctx, node["if"]) else node.get("else", []))
            except NeedChoice:  # the condition needs a choice (e.g. invoke): fine if either branch is possible
                ok = _nodes_ok(ctx, node.get("then", [])) or _nodes_ok(ctx, node.get("else", []))
            if not ok:
                return False
        elif "choose_one" in node:
            if not any(_nodes_ok(ctx, option) for option in node["choose_one"]):
                return False
        elif node.get("required"):
            spec = get_effect(node["do"])
            if spec.can_apply is not None and not spec.can_apply(ctx.state, ctx.seat, node):
                return False
    return True


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
    state: GameState,
    catalog: Catalog,
    seat: int,
    card_uid: str,
    answers: list[Any],
    events: list[Event],
    swap: tuple[str, str] | None = None,
) -> None:
    hand_card = check_play(state, catalog, seat, card_uid)
    if swap is not None:
        check_swap(state, catalog, seat, hand_card, swap)
    card = state.players[seat].hand.take(card_uid)
    if swap is not None:
        card.effective_elements = swapped_elements(catalog, card, swap)
        state.players[seat].element_swap_used = True
        events.append(Event("log.element_swapped", {"seat": seat, "card": card.def_id, "from": swap[0], "to": swap[1]}))
    resolve_played_card(EffectContext(state, catalog, seat, card, events, answers=answers), card)


def _resolve_play(
    base: GameState,
    catalog: Catalog,
    seat: int,
    card_uid: str,
    answers: list[Any],
    swap: tuple[str, str] | None = None,
) -> tuple[GameState, list[Event]]:
    """Play a card from `base` (no pending choice) with the answers given so far.

    Either the card resolves completely, or the result is `base` plus a pending prompt.
    """
    new_state = copy_state(base)
    events: list[Event] = []
    try:
        _play_card(new_state, catalog, seat, card_uid, answers, events, swap)
    except NeedChoice as need:
        waiting = copy_state(base)
        waiting.pending = PendingChoice(seat, card_uid, list(answers), need.prompt, swap)
        return waiting, []
    if reveals_information(events):
        new_state.undo_stack = []  # new checkpoint: can't undo past revealed information
    else:
        card = base.players[seat].hand.find(card_uid)
        new_state.undo_stack.append(UndoEntry(snapshot(base), card.def_id if card else ""))
    return new_state, events


def _resolve_end_turn(
    base: GameState, catalog: Catalog, seat: int, hand_discards: tuple[str, ...], answers: list[Any]
) -> tuple[GameState, list[Event]]:
    """End the turn; if an end-of-turn ability needs a choice, wait for it (replayed like a card)."""
    new_state = copy_state(base)
    new_state.undo_stack = []  # ending the turn commits it; nothing can be undone after this
    events: list[Event] = []
    try:
        end_turn(new_state, catalog, events, hand_discards, answers)
    except NeedChoice as need:
        waiting = copy_state(base)
        waiting.pending = PendingChoice(seat, "", list(answers), need.prompt, None, "end_turn", hand_discards)
        return waiting, []
    return new_state, events


def _resolve_attack(
    base: GameState, catalog: Catalog, seat: int, attacker_uid: str, target_uid: str, answers: list[Any]
) -> tuple[GameState, list[Event]]:
    """Attack; if an on-attack ability needs a choice (e.g. 142 "pay 2 gold for +2 attack"), wait for it."""
    new_state = copy_state(base)
    events: list[Event] = []
    try:
        attack(new_state, catalog, seat, attacker_uid, target_uid, events, answers)
    except NeedChoice as need:
        waiting = copy_state(base)
        waiting.pending = PendingChoice(seat, attacker_uid, list(answers), need.prompt, None, "attack", (), target_uid)
        return waiting, []
    if reveals_information(events):
        new_state.undo_stack = []  # e.g. an on-kill draw: checkpoint
    else:
        unit = next((u for _, u in base.units_of(seat) if u.uid == attacker_uid), None)
        new_state.undo_stack.append(UndoEntry(snapshot(base), unit.def_id if unit else ""))
    return new_state, events


def _respond(state: GameState, catalog: Catalog, action: Respond) -> tuple[GameState, list[Event]]:
    _check_turn(state, action.seat)
    pending = state.pending
    if pending is None:
        raise IllegalAction("error.no_choice_pending")
    base = copy_state(state)
    base.pending = None
    if pending.kind == "end_turn":
        return _resolve_end_turn(base, catalog, pending.seat, pending.hand_discards, [*pending.answers, action.answer])
    if pending.kind == "attack":
        return _resolve_attack(base, catalog, pending.seat, pending.card_uid, pending.target_uid, [*pending.answers, action.answer])
    return _resolve_play(
        base, catalog, pending.seat, pending.card_uid, [*pending.answers, action.answer], pending.swap
    )


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
    if pending.kind == "end_turn":
        return new_state, [Event("log.end_turn_cancelled", {"seat": pending.seat})]
    if pending.kind == "attack":
        return new_state, [Event("log.attack_cancelled", {"seat": pending.seat})]
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
        return _resolve_play(state, catalog, action.seat, action.card_uid, [], action.swap)
    if isinstance(action, Develop):
        _check_turn(state, action.seat)
        option = check_develop(state, catalog, action.seat, action.unit_uid, pay=action.pay)
        new_state = copy_state(state)
        develop_unit(new_state, catalog, action.seat, option, events)
        unit = next(u for _, u in state.units_of(action.seat) if u.uid == action.unit_uid)
        new_state.undo_stack.append(UndoEntry(snapshot(state), unit.def_id))
        return new_state, events
    if isinstance(action, Bank):
        _check_turn(state, action.seat)
        new_state = copy_state(state)
        unit = bank(new_state, catalog, action.seat, action.unit_uid, action.amount, events)
        new_state.undo_stack.append(UndoEntry(snapshot(state), unit.def_id))
        return new_state, events
    if isinstance(action, Attack):
        _check_turn(state, action.seat)
        return _resolve_attack(state, catalog, action.seat, action.attacker_uid, action.target_uid, [])
    if isinstance(action, RemoveCard):
        _check_turn(state, action.seat)
        new_state = copy_state(state)
        card = remove_card(new_state, catalog, action.seat, action.card_uid, events)
        new_state.undo_stack.append(UndoEntry(snapshot(state), card.def_id))
        return new_state, events
    if isinstance(action, (Buy, Refresh)):
        _check_turn(state, action.seat)
        if action.market not in MARKETS:
            raise IllegalAction("error.unknown_market")
        new_state = copy_state(state)
        label = ""
        if isinstance(action, Buy):
            buy(new_state, catalog, action.seat, action.market, action.slot, events, action.pay)
        else:
            refresh(new_state, action.seat, action.market, events)
        if reveals_information(events):
            new_state.undo_stack = []  # a new market card was revealed: checkpoint
        else:
            new_state.undo_stack.append(UndoEntry(snapshot(state), label))
        return new_state, events
    if isinstance(action, EndTurn):
        _check_turn(state, action.seat)
        for uid in action.hand_discards:
            card = state.players[action.seat].hand.find(uid)
            if card is None or not catalog.card(card.def_id).hand_eot or action.hand_discards.count(uid) > 1:
                raise IllegalAction("error.invalid_choice")
        return _resolve_end_turn(state, catalog, action.seat, action.hand_discards, [])
    raise IllegalAction("error.unknown_action")
