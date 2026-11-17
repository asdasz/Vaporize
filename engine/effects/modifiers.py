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
