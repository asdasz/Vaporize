from __future__ import annotations

from engine.effects.registry import get_effect
from tests.helpers import ctx_for, make_game


def test_draw_effect_draws_cards() -> None:
    state = make_game()
    ctx = ctx_for(state)
    hand, deck = len(ctx.player.hand), len(ctx.player.deck)
    get_effect("draw").fn(ctx, {"count": 2})
    assert len(ctx.player.hand) == hand + 2
    assert len(ctx.player.deck) == deck - 2
