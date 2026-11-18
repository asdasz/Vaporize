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
    # Cards like "while in your discard pile: gain 1 VP whenever you kill a unit" (played cards count too).
    killer = ctx.player
    vp = sum(
        (ctx.catalog.card(c.def_id).in_discard or {}).get("vp_per_kill", 0) for c in (*killer.discard, *killer.in_play)
    )
    if vp:
        killer.vp += vp
        ctx.emit("log.gain_vp", seat=ctx.seat, amount=vp)
    if not unit.is_token:
        unit.reset_runtime()
        if any(m.get("shuffle_on_death") for m in ctx.catalog.card(unit.def_id).modifiers):
            owner.deck.put_bottom(unit)  # 795: shuffled back into its owner's deck instead
            owner.deck.shuffle(state.rng)
            ctx.emit("log.shuffled_on_death", card=unit.def_id, owner=unit.owner)
        else:
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
    catalog = ctx.catalog
    # "all your units receive 1 less dmg from all sources" (auras on the owner's board)
    amount -= sum(int(m.get("ally_damage_reduction", 0)) for _, u in ctx.state.units_of(unit.owner) for m in catalog.card(u.def_id).modifiers)
    cap = min((int(m["max_damage_per_hit"]) for m in catalog.card(unit.def_id).modifiers if "max_damage_per_hit" in m), default=None)
    if cap is not None:
        amount = min(amount, cap)  # "takes max. N damage from a single source"
    if amount <= 0:
        return
    unit.current_hp = (unit.current_hp or 0) - amount
    ctx.damaged.append(unit.uid)
    ctx.emit("log.damage", card=unit.def_id, owner=unit.owner, amount=amount)
    if unit.current_hp <= 0 and _cheat_death(ctx, unit):
        return
    if unit.current_hp <= 0:
        destroy_unit(ctx, unit)
        return
    nodes = catalog.card(unit.def_id).triggers.get("on_damage_taken", ())
    if nodes and not unit.is_token:  # e.g. 791 "whenever this unit takes dmg and survives, gain 1 VP"
        from engine.resolver import resolve_effects

        resolve_effects(EffectContext(ctx.state, catalog, unit.owner, unit, ctx.events), nodes)


def _cheat_death(ctx: EffectContext, unit: CardInstance) -> bool:
    """`cheat_death: {element, min}` (793): with enough such cards in the owner's discard pile, survive with 1 HP
    and shuffle the most recent of them into the owner's deck."""
    rule = next((m["cheat_death"] for m in ctx.catalog.card(unit.def_id).modifiers if "cheat_death" in m), None)
    if rule is None:
        return False
    owner = ctx.state.players[unit.owner]
    matching = [c for c in (*owner.discard, *owner.in_play) if rule["element"] in ctx.catalog.card(c.def_id).elements]
    if len(matching) < rule["min"]:
        return False
    unit.current_hp = 1
    card = matching[-1]
    (owner.discard if owner.discard.find(card.uid) else owner.in_play).take(card.uid)
    owner.deck.put_bottom(card)
    owner.deck.shuffle(ctx.state.rng)
    ctx.emit("log.cheated_death", card=unit.def_id, owner=unit.owner, shuffled=card.def_id)
    return True


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
