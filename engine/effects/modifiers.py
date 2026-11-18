"""Effects that change the rest of the turn ("your next spell…", "this turn…")."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect
from engine.values import resolve_value


@effect("next_spell_invoke_bonus", required=("amount",), optional=("element", "element_amount"))
def next_spell_invoke_bonus(ctx: EffectContext, p: dict[str, Any]) -> None:
    """The next spell you play this turn gets +amount invoke (or +element_amount if it has `element`)."""
    ctx.player.turn_modifiers.append(
        {
            "kind": "next_spell_invoke_bonus",
            "amount": resolve_value(ctx, p["amount"]),
            "element": p.get("element"),
            "element_amount": p.get("element_amount", 0),
        }
    )
    ctx.emit("log.next_spell_bonus", seat=ctx.seat)


@effect("next_spell_twice", optional=("vp_per_kill",))
def next_spell_twice(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Your next spell this turn resolves twice with the same invoke value."""
    ctx.player.turn_modifiers.append({"kind": "next_spell_twice", "vp_per_kill": p.get("vp_per_kill", 0)})
    ctx.emit("log.next_spell_twice", seat=ctx.seat)


@effect("boost_attack", required=("amount",))
def boost_attack(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Each of your units on the board gains +amount attack until the end of this turn."""
    amount = resolve_value(ctx, p["amount"])
    for _, unit in ctx.state.units_of(ctx.seat):
        unit.temp_attack += amount
    ctx.emit("log.attack_boosted", seat=ctx.seat, amount=amount)


@effect("vp_per_attack_kill", required=("amount",))
def vp_per_attack_kill(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Until the end of this turn, gain VP whenever one of your units' attacks destroys an enemy unit."""
    ctx.player.turn_modifiers.append({"kind": "vp_per_attack_kill", "amount": resolve_value(ctx, p["amount"])})


@effect("boost_units", required=("target",), optional=("attack", "extra_attacks", "all", "kill_vp"))
def boost_units(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Until the end of this turn: +`attack` and/or `extra_attacks` for one chosen unit (or `all` matching units).
    `kill_vp: N`: you gain N VP if the boosted unit's attack kills a unit this turn."""
    from engine.cardview import attacks_allowed
    from engine.combat import find_unit
    from engine.prompts import Prompt
    from engine.targeting import find_targets

    targets = [u for _, u in find_targets(ctx.state, ctx.seat, p["target"])]
    if not targets:
        return
    attack = resolve_value(ctx, p.get("attack", 0))
    if not p.get("all"):
        uid = ctx.ask(
            Prompt(
                kind="choose_unit",
                key="prompt.boost_unit",
                params={"attack": attack, "extra_attacks": p.get("extra_attacks", 0)},
                options=tuple(u.uid for u in targets),
                allow_skip=True,
            )
        )
        unit = find_unit(ctx.state, uid) if uid else None
        targets = [unit] if unit else []
    for unit in targets:
        unit.temp_attack += attack
        unit.temp_extra_attacks += p.get("extra_attacks", 0)
        if p.get("kill_vp"):
            unit.temp_kill_vp.append([ctx.seat, p["kill_vp"]])
        unit.tapped = unit.attacks_made >= attacks_allowed(unit, ctx.catalog)
        ctx.emit("log.unit_boosted", card=unit.def_id, owner=unit.owner, attack=attack, extra=p.get("extra_attacks", 0))


@effect("boost_self", optional=("attack", "any_tier"))
def boost_self(ctx: EffectContext, p: dict[str, Any]) -> None:
    """The unit playing this ability gets +attack and/or may attack any tier this turn (e.g. 781)."""
    unit = ctx.source
    if unit is None:
        return
    unit.temp_attack += resolve_value(ctx, p.get("attack", 0))
    if p.get("any_tier"):
        unit.temp_any_tier = True
    ctx.emit("log.unit_boosted", card=unit.def_id, owner=unit.owner, attack=p.get("attack", 0), extra=0)


@effect("next_develop_discount")
def next_develop_discount(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Your next development this turn costs 1 less for each prepare you triggered this turn."""
    ctx.player.turn_modifiers.append({"kind": "next_develop_discount_per_prepare"})
    ctx.emit("log.next_develop_discount", seat=ctx.seat)
