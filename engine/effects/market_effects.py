"""Effects on markets: free refreshes, discarding a market card."""

from __future__ import annotations

from typing import Any

from engine.cardview import card_view
from engine.context import EffectContext
from engine.effects.registry import effect
from engine.market import reveal, slide
from engine.prompts import Prompt
from engine.state import MarketState
from engine.values import resolve_value


def _markets(ctx: EffectContext, which: str) -> list[tuple[str, MarketState]]:
    if which == "shared":
        return [("shared", ctx.state.shared_market)]
    if which == "private":
        return [("private", ctx.player.private_market)]
    # "every market": the shared one and every player's private market
    return [("shared", ctx.state.shared_market)] + [("private", p.private_market) for p in ctx.state.players]


@effect("refresh_market", required=("market",), optional=("times", "up_to"))
def refresh_market(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Refresh for free: `times` refreshes, or the player picks 0..`up_to`. `market: all` = every market once."""
    times = resolve_value(ctx, p.get("times", 1))
    if "up_to" in p:
        times = ctx.ask(Prompt(kind="number", key="prompt.refresh_count", params={"market": p["market"]}, min=0, max=p["up_to"]))
    for name, market in _markets(ctx, p["market"]):
        for _ in range(times):
            ctx.emit("log.market_refreshed", seat=ctx.seat, market=name, cost=0)
            slide(ctx.state, market, name, ctx.events)


@effect("discard_from_market", required=("market",))
def discard_from_market(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Choose a card in the market: it goes to the market's removed pile and a new card fills its spot."""
    name, market = _markets(ctx, p["market"])[0]
    cards = market.row.cards()
    if not cards:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_card",
            key="prompt.discard_from_market",
            params={"market": name, "skip_key": "ui.prompt.skip_market_discard"},
            options=tuple(card_view(c, ctx.catalog) for c in cards),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    slot = next(i for i, c in enumerate(market.row.slots) if c is not None and c.uid == uid)
    card = market.row.take(uid)
    market.removed.put_bottom(card)
    ctx.emit("log.market_card_discarded", seat=ctx.seat, card=card.def_id, market=name)
    reveal(ctx.state, market, name, slot, ctx.events)
