"""Effects that delegate to the player's class board."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect


@effect("prepare")
def prepare(ctx: EffectContext, p: dict[str, Any]) -> None:
    from engine.resolver import resolve_effects  # local import: resolver imports this package

    ctx.emit("log.prepare", seat=ctx.seat)
    resolve_effects(ctx, ctx.class_def.prepare)
