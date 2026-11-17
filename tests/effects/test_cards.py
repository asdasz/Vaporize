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


def test_scout_reveals_and_draws_chosen_card_keeping_order() -> None:
    import pytest

    from engine.prompts import NeedChoice
    from tests.helpers import make_cards

    state = make_game()
    ctx = ctx_for(state)
    ctx.player.deck.cards = make_cards(state, ctx.seat, ["MAG-S01", "MAG-S05", "MAG-S06", "MAG-S07"])
    top = [c.uid for c in ctx.player.deck]
    with pytest.raises(NeedChoice) as need:
        get_effect("scout").fn(ctx, {"count": 3, "draw": 1})
    prompt = need.value.prompt
    assert [o["uid"] for o in prompt.options] == top[:3]
    assert prompt.cancellable is False
    ctx = ctx_for(state)
    ctx.answers = [top[1]]
    hand_before = len(ctx.player.hand)
    get_effect("scout").fn(ctx, {"count": 3, "draw": 1})
    assert [c.uid for c in ctx.player.deck] == [top[0], top[2], top[3]]
    assert len(ctx.player.hand) == hand_before + 1


def test_scout_uses_only_cards_left_in_deck() -> None:
    from tests.helpers import make_cards

    state = make_game()
    ctx = ctx_for(state)
    ctx.player.deck.cards = make_cards(state, ctx.seat, ["MAG-S01", "MAG-S02"])
    ctx.answers = [None]  # skip drawing
    get_effect("scout").fn(ctx, {"count": 5, "draw": 1})
    assert ctx.events[0].params["count"] == 2
