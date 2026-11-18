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


@effect("scout", required=("count",), optional=("draw", "discard_any"))
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
    if p.get("discard_any"):
        chosen = ctx.ask(
            Prompt(
                kind="choose_cards",
                key="prompt.scout_discard",
                params={"count": len(cards)},
                options=tuple(card_view(c, ctx.catalog) for c in cards),
                min=0,
                max=len(cards),
                cancellable=False,
            )
        )
        for uid in chosen:
            ctx.player.discard.put_bottom(deck.take(uid))
        if chosen:
            ctx.emit("log.scout_discarded", seat=ctx.seat, count=len(chosen))
        return
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


@effect("discard_from_hand", optional=("then",))
def discard_from_hand(ctx: EffectContext, p: dict[str, Any]) -> None:
    """You may discard 1 card from your hand (keeping the 2-card minimum). If you do, resolve `then`."""
    from engine.resolver import resolve_effects  # local import: resolver imports this package
    from engine.rules import MIN_HAND

    hand = ctx.player.hand
    if len(hand) <= MIN_HAND:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_card",
            key="prompt.discard_from_hand",
            params={"skip_key": "ui.prompt.skip_discard"},
            options=tuple(card_view(c, ctx.catalog) for c in hand),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    card = hand.take(uid)
    ctx.player.discard.put_bottom(card)
    ctx.emit("log.discarded_from_hand", seat=ctx.seat, card=card.def_id)
    resolve_effects(ctx, p.get("then", []))


@effect("move_played_to_deck", optional=("element", "position"))
def move_played_to_deck(ctx: EffectContext, p: dict[str, Any]) -> None:
    """You may put one of your other cards played this turn (optionally of an element) on top/bottom of your deck."""
    from engine.elements import elements_of

    source_uid = ctx.source.uid if ctx.source else None
    element = p.get("element")
    options = [
        c for c in ctx.player.in_play if c.uid != source_uid and (element is None or element in elements_of(c, ctx.catalog))
    ]
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_card",
            key="prompt.move_played_to_deck",
            params={"skip_key": "ui.prompt.skip_move", "position": p.get("position", "bottom")},
            options=tuple(card_view(c, ctx.catalog) for c in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    card = ctx.player.in_play.take(uid)
    card.effective_elements = None
    if p.get("position", "bottom") == "top":
        ctx.player.deck.put_top(card)
    else:
        ctx.player.deck.put_bottom(card)
    ctx.emit("log.moved_to_deck", seat=ctx.seat, card=card.def_id, position=p.get("position", "bottom"))
