"""Effects that delegate to the player's class board."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect


@effect("prepare", optional=("times", "exceed_limit"))
def prepare(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Use the class's prepare `times` times. With `exceed_limit`, resource gains may pass the class limit."""
    from engine.resolver import resolve_effects  # local import: resolver imports this package

    from engine.values import resolve_value  # local import: values -> invoke -> context

    times = resolve_value(ctx, p.get("times", 1))
    if times <= 0:
        return
    ctx.emit("log.prepare", seat=ctx.seat, times=times)
    before, ctx.exceed_limit = ctx.exceed_limit, bool(p.get("exceed_limit"))
    try:
        for _ in range(times):
            ctx.player.prepares_this_turn += 1
            resolve_effects(ctx, ctx.class_def.prepare)
    finally:
        ctx.exceed_limit = before
