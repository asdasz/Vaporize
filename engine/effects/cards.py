"""Card-flow effects: draw, scout, disrupt, ..."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.drawing import draw_cards
from engine.effects.registry import effect


@effect("draw", required=("count",))
def draw(ctx: EffectContext, p: dict[str, Any]) -> None:
    draw_cards(ctx.state, ctx.seat, p["count"], ctx.events)
