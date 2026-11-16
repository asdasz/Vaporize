"""Turn sequencing: start of turn -> actions -> end of turn, rounds and game end."""

from __future__ import annotations

from engine.catalog import Catalog
from engine.context import EffectContext
from engine.drawing import draw_up_to
from engine.events import Event
from engine.resolver import resolve_effects
from engine.rules import HAND_SIZE, VP_GOAL
from engine.state import GameState


def _run_class_trigger(state: GameState, catalog: Catalog, seat: int, trigger: str, events: list[Event]) -> None:
    cdef = catalog.cls(state.players[seat].class_id)
    for passive in cdef.passives:
        if passive.get("trigger") == trigger:
            ctx = EffectContext(state, catalog, seat, None, events)
            resolve_effects(ctx, passive.get("effects", []))


def _run_unit_triggers(state: GameState, catalog: Catalog, seat: int, trigger: str, events: list[Event]) -> None:
    for _, unit in state.units_of(seat):
        if unit.is_token:
            continue
        nodes = catalog.card(unit.def_id).triggers.get(trigger, ())
        if nodes:
            resolve_effects(EffectContext(state, catalog, seat, unit, events), nodes)


def start_turn(state: GameState, catalog: Catalog, events: list[Event]) -> None:
    player = state.current_player
    player.inf = 0
    player.played_this_turn = []
    player.free_refresh_used = False
    player.element_swap_used = False
    events.append(Event("log.turn_started", {"seat": player.seat, "round": state.round}))
    _run_class_trigger(state, catalog, player.seat, "sot", events)
    _run_unit_triggers(state, catalog, player.seat, "sot", events)


def score_units(state: GameState, catalog: Catalog, seat: int, events: list[Event]) -> int:
    tiers = catalog.cls(state.players[seat].class_id).tiers
    gained = sum(tiers[tier].vp for tier, unit in state.units_of(seat) if not unit.is_token)
    if gained:
        state.players[seat].vp += gained
        events.append(Event("log.vp_scored", {"seat": seat, "amount": gained}))
    return gained


def end_turn(state: GameState, catalog: Catalog, events: list[Event]) -> None:
    player = state.current_player
    seat = player.seat
    # 1. Score: EOT effects, then VP for units on tiers.
    _run_class_trigger(state, catalog, seat, "eot", events)
    _run_unit_triggers(state, catalog, seat, "eot", events)
    score_units(state, catalog, seat, events)
    # 2. Untap and remove one stun / freeze token.
    for _, unit in state.units_of(seat):
        unit.tapped = False
        for status in ("stun", "freeze"):
            if unit.status[status] > 0:
                unit.status[status] -= 1
    # 3. Clean up: played cards go to the discard pile, unspent inf is lost.
    player.discard.cards.extend(player.in_play.take_all())
    player.inf = 0
    player.played_this_turn = []
    # 4. Draw back up to 7.
    draw_up_to(state, seat, HAND_SIZE, events)
    events.append(Event("log.turn_ended", {"seat": seat}))
    _advance(state, catalog, events)


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
