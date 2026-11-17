"""Card-flow effects: draw, scout, ..."""

from __future__ import annotations

from typing import Any

from engine.cardview import card_view
from engine.context import EffectContext
from engine.drawing import draw_cards, reshuffle_discard
from engine.effects.registry import effect
from engine.prompts import Prompt
from engine.values import resolve_value


@effect("draw", required=("count",))
def draw(ctx: EffectContext, p: dict[str, Any]) -> None:
    draw_cards(ctx.state, ctx.seat, resolve_value(ctx, p["count"]), ctx.events)


@effect("scout", required=("count",), optional=("draw",))
def scout(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Look at the top X cards (fewer if the deck is short). With `draw: 1`, draw one of them;
    the rest stay on top in the same order."""
    count = resolve_value(ctx, p["count"])
    if count <= 0:
        return
    deck = ctx.player.deck
    if deck.is_empty():
        reshuffle_discard(ctx.state, ctx.seat, ctx.events)
    cards = deck.cards[:count]
    if not cards:
        return
    ctx.emit("log.scouted", seat=ctx.seat, count=len(cards))
    if not p.get("draw"):
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_card",
            key="prompt.scout_draw",
            params={"count": len(cards)},
            options=tuple(card_view(c, ctx.catalog) for c in cards),
            allow_skip=True,
            cancellable=False,  # the player has seen the cards now
        )
    )
    if uid is not None:
        ctx.player.hand.put_bottom(deck.take(uid))
        ctx.emit("log.cards_drawn", seat=ctx.seat, count=1)
