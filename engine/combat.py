"""Damage, healing and destruction of units."""

from __future__ import annotations

from engine.cards import CardInstance
from engine.context import EffectContext
from engine.state import GameState


def find_unit(state: GameState, uid: str) -> CardInstance | None:
    for player in state.players:
        for _, unit in state.units_of(player.seat):
            if unit.uid == uid:
                return unit
    return None


def destroy_unit(ctx: EffectContext, unit: CardInstance) -> None:
    """Remove a unit from the board. Cards go to the owner's discard pile; tokens are deleted."""
    state = ctx.state
    owner = state.players[unit.owner]
    if owner.tokens.find(unit.uid):
        owner.tokens.take(unit.uid)
    elif state.tier4.find(unit.uid):
        state.tier4.take(unit.uid)
    else:
        for row in owner.tiers.values():
            if row.find(unit.uid):
                row.take(unit.uid)
                break
    ctx.emit("log.unit_destroyed", card=unit.def_id, owner=unit.owner)
    ctx.kills += 1
    if unit.owner != ctx.seat:
        ctx.player.enemy_kills_this_turn += 1
    if not unit.is_token:
        unit.reset_runtime()
        owner.discard.put_bottom(unit)


def damage_unit(ctx: EffectContext, uid: str, amount: int) -> None:
    """One instance of damage. A shield token absorbs the whole hit."""
    unit = find_unit(ctx.state, uid)
    if unit is None or amount <= 0:
        return
    if unit.status["shield"] > 0:
        unit.status["shield"] -= 1
        ctx.emit("log.shield_absorbed", card=unit.def_id, owner=unit.owner)
        return
    unit.current_hp = (unit.current_hp or 0) - amount
    ctx.emit("log.damage", card=unit.def_id, owner=unit.owner, amount=amount)
    if unit.current_hp <= 0:
        destroy_unit(ctx, unit)


def heal_unit(ctx: EffectContext, uid: str, amount: int, max_hp: int | None = None) -> None:
    """Add HP tokens. With `max_hp`, healing stops there but never lowers a unit that is already above it."""
    unit = find_unit(ctx.state, uid)
    if unit is None or amount <= 0:
        return
    before = unit.current_hp or 0
    after = before + amount
    if max_hp is not None:
        after = max(before, min(after, max_hp))
    unit.current_hp = after
    ctx.emit("log.heal", card=unit.def_id, owner=unit.owner, amount=after - before)
