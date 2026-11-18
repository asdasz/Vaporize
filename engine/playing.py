"""Resolving a played card: unit stats, effects, "next spell" modifiers and after-play triggers.

Used for cards played from the hand and for cards played by other effects (e.g. from the discard pile).
"""

from __future__ import annotations

from engine.cards import CardInstance
from engine.context import EffectContext
from engine.elements import elements_of
from engine.events import Event
from engine.resolver import resolve_effects
from engine.state import PlayedCard
from engine.values import resolve_value


def _take_next_spell_modifiers(ctx: EffectContext) -> tuple[bool, int]:
    """Apply and consume "your next spell …" modifiers. Returns (resolve twice, VP per kill)."""
    player = ctx.player
    assert ctx.source is not None
    printed = ctx.catalog.card(ctx.source.def_id).elements  # element changes don't count
    twice, vp_per_kill, keep = False, 0, []
    for mod in player.turn_modifiers:
        if mod["kind"] == "next_spell_invoke_bonus":
            element = mod.get("element")
            ctx.invoke_extra += mod.get("element_amount", 0) if element and element in printed else mod["amount"]
        elif mod["kind"] == "next_spell_twice":
            twice = True
            vp_per_kill += mod.get("vp_per_kill", 0)
        else:
            keep.append(mod)
    player.turn_modifiers = keep
    return twice, vp_per_kill


def resolve_played_card(ctx: EffectContext, card: CardInstance) -> None:
    """The card has already left its zone. Put it into play, record it as played and resolve it.

    `ctx.source` must be `card`; prompts use `ctx.answers` (shared with any parent resolution).
    """
    state, catalog, seat = ctx.state, ctx.catalog, ctx.seat
    player = state.players[seat]
    cdef = catalog.card(card.def_id)
    player.played_this_turn.append(PlayedCard(card.uid, cdef.id, elements_of(card, catalog)))
    twice, vp_per_kill = _take_next_spell_modifiers(ctx) if cdef.type == "spell" else (False, 0)

    if cdef.is_unit:
        player.tiers[1].place(card)
        resolve_effects(ctx, cdef.pre_effects)  # e.g. 779 "prepare x2 before setting its HP"
        attack = resolve_value(ctx, cdef.attack if cdef.attack is not None else 0)
        health = resolve_value(ctx, cdef.health if cdef.health is not None else 1)
        card.fixed_attack, card.fixed_health, card.current_hp = attack, health, health
        ctx.emit("log.unit_played", seat=seat, card=cdef.id, tier=1)
    else:
        player.in_play.put_bottom(card)
        ctx.emit("log.card_played", seat=seat, card=cdef.id)

    for _ in range(2 if twice else 1):
        resolve_effects(ctx, cdef.effects)
    if vp_per_kill and ctx.kills:
        player.vp += vp_per_kill * ctx.kills
        ctx.emit("log.gain_vp", seat=seat, amount=vp_per_kill * ctx.kills)

    run_card_played_triggers(ctx)


def run_card_played_triggers(ctx: EffectContext) -> None:
    """Units with an `on_card_played` trigger react after each card their owner plays."""
    for _, unit in ctx.state.units_of(ctx.seat):
        nodes = ctx.catalog.card(unit.def_id).triggers.get("on_card_played", ())
        if nodes and not unit.is_token:
            child = ctx.child(unit)
            resolve_effects(child, nodes)
            ctx.adopt(child)


def play_card_from_effect(ctx: EffectContext, card: CardInstance, events: list[Event] | None = None) -> None:
    """Play `card` (already removed from its zone) as part of another card's effect."""
    child = ctx.child(card)
    resolve_played_card(child, card)
    ctx.kills += child.kills
    ctx.adopt(child)
