from __future__ import annotations

from engine.effects.registry import get_effect
from tests.helpers import ctx_for, make_game


def test_gain_inf() -> None:
    state = make_game()
    ctx = ctx_for(state)
    get_effect("gain_inf").fn(ctx, {"amount": 2})
    assert ctx.player.inf == 2


def test_gain_resource_card_effect_can_exceed_limit_up_to_hard_max() -> None:
    state = make_game()
    ctx = ctx_for(state)
    ctx.player.resource = 4
    get_effect("gain_resource").fn(ctx, {"amount": 5})
    assert ctx.player.resource == 7


def test_gain_resource_up_to_limit() -> None:
    state = make_game()
    ctx = ctx_for(state)
    ctx.player.resource = 3
    get_effect("gain_resource").fn(ctx, {"amount": 3, "up_to_limit": True})
    assert ctx.player.resource == 4


def test_gain_resource_up_to_limit_never_reduces() -> None:
    state = make_game()
    ctx = ctx_for(state)
    ctx.player.resource = 6
    get_effect("gain_resource").fn(ctx, {"amount": 1, "up_to_limit": True})
    assert ctx.player.resource == 6


def test_lose_resource_floors_at_zero() -> None:
    state = make_game()
    ctx = ctx_for(state)
    ctx.player.resource = 1
    get_effect("lose_resource").fn(ctx, {"amount": 3})
    assert ctx.player.resource == 0


def test_gain_vp() -> None:
    state = make_game()
    ctx = ctx_for(state)
    get_effect("gain_vp").fn(ctx, {"amount": 2})
    assert ctx.player.vp == 2
