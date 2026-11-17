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
            params={"count": len(cards), "skip_key": "ui.prompt.skip_draw"},
            options=tuple(card_view(c, ctx.catalog) for c in cards),
            allow_skip=True,
            cancellable=False,  # the player has seen the cards now
        )
    )
    if uid is not None:
        ctx.player.hand.put_bottom(deck.take(uid))
        ctx.emit("log.cards_drawn", seat=ctx.seat, count=1)


@effect("play_from_discard", optional=("card_type",))
def play_from_discard(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Play a card (e.g. a spell) from your discard pile that hasn't been played this turn."""
    from engine.playing import play_card_from_effect  # local import: playing -> resolver -> effects

    played = {x.uid for x in ctx.player.played_this_turn}
    wanted = p.get("card_type")
    options = [
        c
        for c in ctx.player.discard
        if c.uid not in played and (wanted is None or ctx.catalog.card(c.def_id).type == wanted)
    ]
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_card",
            key="prompt.play_from_discard",
            params={"skip_key": "ui.prompt.skip_play"},
            options=tuple(card_view(c, ctx.catalog) for c in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    card = ctx.player.discard.take(uid)
    ctx.emit("log.played_from_discard", seat=ctx.seat, card=card.def_id)
    play_card_from_effect(ctx, card)
