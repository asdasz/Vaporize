"""Turn sequencing: start of turn -> actions -> end of turn, rounds and game end."""

from __future__ import annotations

from typing import Any

from engine.catalog import Catalog
from engine.context import EffectContext
from engine.development import eot_vp
from engine.drawing import draw_up_to
from engine.effects.economy import convert_unspent_inf
from engine.events import Event
from engine.resolver import resolve_effects
from engine.rules import HAND_SIZE, VP_GOAL
from engine.state import GameState


class Answers:
    """Answers shared by every trigger resolved during one end of turn (replayed like a card)."""

    def __init__(self, answers: list[Any] | None = None) -> None:
        self.answers = list(answers or [])
        self.index = 0


def _run(state: GameState, catalog: Catalog, seat: int, source: Any, nodes: Any, events: list[Event], answers: Answers | None) -> None:
    ctx = EffectContext(state, catalog, seat, source, events, answers.answers if answers else [], answers.index if answers else 0)
    resolve_effects(ctx, nodes)
    if answers:
        answers.index = ctx.answer_index


def _run_class_trigger(
    state: GameState, catalog: Catalog, seat: int, trigger: str, events: list[Event], answers: Answers | None = None
) -> None:
    cdef = catalog.cls(state.players[seat].class_id)
    for passive in cdef.passives:
        if passive.get("trigger") == trigger:
            _run(state, catalog, seat, None, passive.get("effects", []), events, answers)


def _run_unit_triggers(
    state: GameState, catalog: Catalog, seat: int, trigger: str, events: list[Event], answers: Answers | None = None
) -> None:
    for _, unit in state.units_of(seat):
        if unit.is_token:
            continue
        nodes = catalog.card(unit.def_id).triggers.get(trigger, ())
        if nodes:
            _run(state, catalog, seat, unit, nodes, events, answers)


def start_turn(state: GameState, catalog: Catalog, events: list[Event]) -> None:
    player = state.current_player
    player.inf = 0
    player.played_this_turn = []
    player.turn_modifiers = []
    player.turn_flags = []
    player.prepares_this_turn = 0
    player.enemy_kills_this_turn = 0
    player.locked_cards = []
    player.removals_this_turn = 0
    player.turn_modifiers = []
    player.turn_flags = []
    player.prepares_this_turn = 0
    player.enemy_kills_this_turn = 0
    player.locked_cards = []
    player.removals_this_turn = 0
    player.free_refresh_used = False
    player.element_swap_used = False
    player.develop_inf = 0
    cdef = catalog.cls(player.class_id)
    player.any_tier_attacks = sum(1 for p in cdef.passives if p.get("modifier") == "any_tier_attack_once_per_turn")
    events.append(Event("log.turn_started", {"seat": player.seat, "round": state.round}))
    _run_class_trigger(state, catalog, player.seat, "sot", events)
    _run_unit_triggers(state, catalog, player.seat, "sot", events)


def score_units(state: GameState, catalog: Catalog, seat: int, events: list[Event]) -> int:
    gained = eot_vp(state, catalog, seat)  # every unit scores by its tier, tokens included
    if gained:
        state.players[seat].vp += gained
        events.append(Event("log.vp_scored", {"seat": seat, "amount": gained}))
    return gained


def end_turn(
    state: GameState,
    catalog: Catalog,
    events: list[Event],
    hand_discards: tuple[str, ...] = (),
    answers: list[Any] | None = None,
) -> None:
    """End the current player's turn. EOT triggers may ask questions (NeedChoice); the caller replays with
    `answers`, like playing a card."""
    shared = Answers(answers)
    player = state.current_player
    seat = player.seat
    # 1. Score: hand cards with an end-of-turn ability (chosen by the player), EOT effects, unit VP.
    for uid in hand_discards:
        card = player.hand.take(uid)  # may break the 2-card minimum (the card says so)
        vp = (catalog.card(card.def_id).hand_eot or {}).get("discard_for_vp", 0)
        player.discard.put_bottom(card)
        player.vp += vp
        events.append(Event("log.hand_eot_discard", {"seat": seat, "card": card.def_id, "vp": vp}))
    # Unit EOT abilities go before the class's (so e.g. a unit can still invoke with mana the Mage loses at EOT).
    _run_unit_triggers(state, catalog, seat, "eot", events, shared)
    convert_unspent_inf(EffectContext(state, catalog, seat, None, events))  # 133: before tax
    _run_class_trigger(state, catalog, seat, "eot", events, shared)
    score_units(state, catalog, seat, events)
    _grow_banks(state, catalog, seat, events)
    # 2. Untap and remove one stun / freeze token.
    for _, unit in state.units_of(seat):
        unit.tapped = False
        unit.attacks_made = 0
        unit.temp_attack = 0  # "this turn" attack bonuses end
        unit.temp_extra_attacks = 0
        unit.temp_any_tier = False
        unit.temp_kill_vp = []
        for status in ("stun", "freeze"):
            if unit.status[status] > 0:
                unit.status[status] -= 1
    # 3. Clean up: played cards go to the discard pile, unspent inf is lost.
    for card in player.in_play:
        card.effective_elements = None  # an element swap only lasts while the card is in play
    player.discard.cards.extend(player.in_play.take_all())
    player.inf = 0
    player.develop_inf = 0
    player.any_tier_attacks = 0
    player.played_this_turn = []
    player.turn_modifiers = []
    player.turn_flags = []
    player.prepares_this_turn = 0
    player.enemy_kills_this_turn = 0
    player.locked_cards = []
    player.removals_this_turn = 0
    # 4. Draw back up to 7.
    draw_up_to(state, seat, HAND_SIZE, events)
    events.append(Event("log.turn_ended", {"seat": seat}))
    _advance(state, catalog, events)


def _grow_banks(state: GameState, catalog: Catalog, seat: int, events: list[Event]) -> None:
    """143: "at the end of your turn, double the gold on this card" (it isn't taxed)."""
    for _, unit in state.units_of(seat):
        if unit.stored > 0 and any(m.get("resource_bank") for m in catalog.card(unit.def_id).modifiers):
            unit.stored *= 2
            events.append(Event("log.bank_doubled", {"seat": seat, "card": unit.def_id, "amount": unit.stored}))


def _advance(state: GameState, catalog: Catalog, events: list[Event]) -> None:
    nxt = (state.current + 1) % len(state.players)
    if nxt == state.first_player:
        if any(p.vp >= VP_GOAL for p in state.players):
            _finish(state, events)
            return
        state.round += 1
        events.append(Event("log.round_started", {"round": state.round}))
    state.current = nxt
    start_turn(state, catalog, events)


def highest_tier(state: GameState, seat: int) -> int:
    return max((tier for tier, _ in state.units_of(seat)), default=0)


def compute_winners(state: GameState) -> list[int]:
    best = max(p.vp for p in state.players)
    tied = [p.seat for p in state.players if p.vp == best]
    if len(tied) > 1:
        top = max(highest_tier(state, s) for s in tied)
        tied = [s for s in tied if highest_tier(state, s) == top]
    return tied


def _finish(state: GameState, events: list[Event]) -> None:
    state.phase = "game_over"
    state.winners = compute_winners(state)
    events.append(Event("log.game_over", {"winners": list(state.winners)}))
