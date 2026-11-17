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
