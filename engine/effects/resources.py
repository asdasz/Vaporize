"""Resource effects: inf, class resource, VP."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect


@effect("gain_inf", required=("amount",))
def gain_inf(ctx: EffectContext, p: dict[str, Any]) -> None:
    ctx.player.inf += p["amount"]
    ctx.emit("log.gain_inf", seat=ctx.seat, amount=p["amount"])


@effect("gain_resource", required=("amount",), optional=("up_to_limit",))
def gain_resource(ctx: EffectContext, p: dict[str, Any]) -> None:
    rule = ctx.class_def.resource
    cap = rule.limit if p.get("up_to_limit") else rule.hard_max
    before = ctx.player.resource
    after = before + p["amount"]
    if cap is not None:
        after = min(after, max(cap, before))  # never reduce a value already above the cap
    ctx.player.resource = after
    ctx.emit("log.gain_resource", seat=ctx.seat, amount=after - before, resource=rule.key)


@effect("lose_resource", required=("amount",))
def lose_resource(ctx: EffectContext, p: dict[str, Any]) -> None:
    before = ctx.player.resource
    ctx.player.resource = max(0, before - p["amount"])
    lost = before - ctx.player.resource
    ctx.emit("log.lose_resource", seat=ctx.seat, amount=lost, resource=ctx.class_def.resource.key)


@effect("gain_vp", required=("amount",))
def gain_vp(ctx: EffectContext, p: dict[str, Any]) -> None:
    ctx.player.vp += p["amount"]
    ctx.emit("log.gain_vp", seat=ctx.seat, amount=p["amount"])
