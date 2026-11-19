"""Class-resource economy effects (Monarch gold): tax, paying the resource for effects, converting inf."""

from __future__ import annotations

from typing import Any

from engine.combat import damage_unit
from engine.context import EffectContext
from engine.effects.registry import effect
from engine.prompts import Prompt
from engine.targeting import find_targets
from engine.values import resolve_value


def resource_cap(ctx: EffectContext) -> int | None:
    return ctx.class_def.resource.hard_max


@effect("pay_tax", optional=("per",))
def pay_tax(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Monarch end of turn: pay 1 resource for every `per` (4) you have. Skipped by "you pay no tax" (135).

    Resource kept on units (`resource_bank`, 143) isn't taxed. Units with `vp_per_tax` (144) give VP per tax paid.
    """
    player = ctx.player
    if any(m["kind"] == "skip_tax" for m in player.turn_modifiers):
        ctx.emit("log.tax_skipped", seat=ctx.seat)
        return
    tax = min(player.resource, player.resource // int(p.get("per", 4)))
    if tax <= 0:
        return
    player.resource -= tax
    ctx.emit("log.tax_paid", seat=ctx.seat, amount=tax, resource=ctx.class_def.resource.key)
    vp = tax * sum(int(m.get("vp_per_tax", 0)) for _, u in ctx.state.units_of(ctx.seat) for m in ctx.catalog.card(u.def_id).modifiers)
    if vp:
        player.vp += vp
        ctx.emit("log.gain_vp", seat=ctx.seat, amount=vp)


def tax_preview(ctx: EffectContext, per: int = 4) -> int:
    """Tax the player would pay at the end of this turn right now (for the UI)."""
    if any(m["kind"] == "skip_tax" for m in ctx.player.turn_modifiers):
        return 0
    return ctx.player.resource // per


@effect("skip_tax")
def skip_tax(ctx: EffectContext, p: dict[str, Any]) -> None:
    """135: you pay no tax at the end of this turn."""
    ctx.player.turn_modifiers.append({"kind": "skip_tax"})
    ctx.emit("log.skip_tax", seat=ctx.seat)


@effect("convert_inf_eot")
def convert_inf_eot(ctx: EffectContext, p: dict[str, Any]) -> None:
    """133: at the end of this turn, all unspent inf becomes class resource (before tax)."""
    if not any(m["kind"] == "convert_inf_eot" for m in ctx.player.turn_modifiers):
        ctx.player.turn_modifiers.append({"kind": "convert_inf_eot"})
    ctx.emit("log.convert_inf_eot", seat=ctx.seat, resource=ctx.class_def.resource.key)


def convert_unspent_inf(ctx: EffectContext) -> None:
    """Called by the end of turn (engine/turn.py) when `convert_inf_eot` was played."""
    player = ctx.player
    if not any(m["kind"] == "convert_inf_eot" for m in player.turn_modifiers) or player.inf <= 0:
        return
    cap = resource_cap(ctx)
    gained = player.inf if cap is None else max(0, min(player.inf, cap - player.resource))
    player.resource += gained
    ctx.emit("log.inf_converted", seat=ctx.seat, inf=player.inf, amount=gained, resource=ctx.class_def.resource.key)
    player.inf = 0


def _can_pay_resource(state: Any, seat: int, p: dict[str, Any]) -> bool:
    return state.players[seat].resource >= int(p.get("cost", 1))


@effect("paid_damage", required=("amount", "target"), optional=("cost",), can_apply=_can_pay_resource)
def paid_damage(ctx: EffectContext, p: dict[str, Any]) -> None:
    """139: "spend 1 gold to deal 1 dmg to an enemy unit, repeat as many times as you want".

    Each round asks for a target (or Stop); picking one pays `cost` resource and deals `amount` damage.
    """
    cost = int(p.get("cost", 1))
    amount = resolve_value(ctx, p["amount"])
    hits = 0
    while ctx.player.resource >= cost:
        targets = find_targets(ctx.state, ctx.seat, p["target"])
        if not targets:
            break
        uid = ctx.ask(
            Prompt(
                kind="choose_unit",
                key="prompt.paid_damage",
                params={"amount": amount, "cost": cost, "resource": ctx.class_def.resource.key, "hits": hits, "skip_key": "ui.prompt.stop"},
                options=tuple(unit.uid for _, unit in targets),
                allow_skip=True,
            )
        )
        if uid is None:
            break
        ctx.player.resource -= cost
        ctx.emit("log.paid_resource", seat=ctx.seat, amount=cost, resource=ctx.class_def.resource.key)
        damage_unit(ctx, uid, amount)
        hits += 1


@effect("pay_resource_times", required=("cost", "times", "effects"))
def pay_resource_times(ctx: EffectContext, p: dict[str, Any]) -> None:
    """142: "you can pay 2 gold to … up to 2 times": choose how many times (0..N) to pay `cost` and resolve `effects`."""
    from engine.resolver import resolve_effects  # local import: resolver imports this package

    cost = int(p["cost"])
    most = min(resolve_value(ctx, p["times"]), ctx.player.resource // cost) if cost > 0 else resolve_value(ctx, p["times"])
    if most <= 0:
        return
    times = ctx.ask(
        Prompt(
            kind="number",
            key="prompt.pay_resource_times",
            params={"cost": cost, "resource": ctx.class_def.resource.key, "card": ctx.source.def_id if ctx.source else None},
            min=0,
            max=most,
        )
    )
    if times <= 0:
        return
    ctx.player.resource -= cost * times
    ctx.emit("log.paid_resource", seat=ctx.seat, amount=cost * times, resource=ctx.class_def.resource.key)
    for _ in range(times):
        resolve_effects(ctx, p["effects"])
