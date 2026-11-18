"""Resource effects: inf, class resource, VP."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect
from engine.values import resolve_value


@effect("gain_inf", required=("amount",))
def gain_inf(ctx: EffectContext, p: dict[str, Any]) -> None:
    amount = resolve_value(ctx, p["amount"])
    ctx.player.inf += amount
    ctx.emit("log.gain_inf", seat=ctx.seat, amount=amount)


@effect("gain_resource", required=("amount",), optional=("up_to_limit",))
def gain_resource(ctx: EffectContext, p: dict[str, Any]) -> None:
    rule = ctx.class_def.resource
    cap = rule.limit if p.get("up_to_limit") and not ctx.exceed_limit else rule.hard_max
    before = ctx.player.resource
    after = before + resolve_value(ctx, p["amount"])
    if cap is not None:
        after = min(after, max(cap, before))  # never reduce a value already above the cap
    ctx.player.resource = after
    ctx.emit("log.gain_resource", seat=ctx.seat, amount=after - before, resource=rule.key)


@effect("lose_resource", required=("amount",))
def lose_resource(ctx: EffectContext, p: dict[str, Any]) -> None:
    before = ctx.player.resource
    ctx.player.resource = max(0, before - resolve_value(ctx, p["amount"]))
    lost = before - ctx.player.resource
    ctx.emit("log.lose_resource", seat=ctx.seat, amount=lost, resource=ctx.class_def.resource.key)


@effect("gain_vp", required=("amount",))
def gain_vp(ctx: EffectContext, p: dict[str, Any]) -> None:
    amount = resolve_value(ctx, p["amount"])
    ctx.player.vp += amount
    ctx.emit("log.gain_vp", seat=ctx.seat, amount=amount)


def _can_pay(state: Any, seat: int, p: dict[str, Any]) -> bool:
    amount = p["amount"]
    return not isinstance(amount, int) or state.players[seat].inf >= amount


@effect("pay_inf", required=("amount",), can_apply=_can_pay)
def pay_inf(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Spend inf as part of a card (e.g. "you can pay 3 inf to …"). Fails if you can't pay."""
    from engine.errors import IllegalAction

    amount = resolve_value(ctx, p["amount"])
    if ctx.player.inf < amount:
        raise IllegalAction("error.not_enough_inf", cost=amount)
    ctx.player.inf -= amount
    ctx.emit("log.paid_inf", seat=ctx.seat, amount=amount)


@effect("others_lose_vp", required=("amount",))
def others_lose_vp(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Every other player loses VP (never below 0)."""
    amount = resolve_value(ctx, p["amount"])
    for player in ctx.state.players:
        if player.seat != ctx.seat:
            lost = min(player.vp, amount)
            player.vp -= lost
            ctx.emit("log.lose_vp", seat=player.seat, amount=lost)


@effect("influence_bonus", required=("amount",))
def influence_bonus(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Each other influence card you play later this turn gives `amount` extra inf."""
    ctx.player.turn_modifiers.append(
        {"kind": "influence_bonus", "amount": resolve_value(ctx, p["amount"]), "source": ctx.source.uid if ctx.source else None}
    )
