from __future__ import annotations

import pytest

from engine.effects.registry import get_effect
from engine.invoke import invoke
from engine.prompts import NeedChoice
from tests.helpers import ctx_for, make_cards, make_game


def test_prepare_gains_one_mana_up_to_limit() -> None:
    state = make_game()
    ctx = ctx_for(state)
    ctx.player.resource = 3
    get_effect("prepare").fn(ctx, {})
    assert ctx.player.resource == 4
    get_effect("prepare").fn(ctx, {})
    assert ctx.player.resource == 4


def test_mage_invoke_spends_mana_and_spells_get_plus_one() -> None:
    state = make_game()
    spell = make_cards(state, state.current, ["MAG-S010"])[0]
    ctx = ctx_for(state, source=spell)
    ctx.player.resource = 3
    with pytest.raises(NeedChoice) as need:
        invoke(ctx)
    assert (need.value.prompt.min, need.value.prompt.max, need.value.prompt.params["bonus"]) == (0, 3, 1)
    ctx.answers = [2]
    assert invoke(ctx) == 3
    assert ctx.player.resource == 1
    assert invoke(ctx) == 3  # cached: a card invokes once


def test_invoke_without_mana_does_not_ask() -> None:
    state = make_game()
    spell = make_cards(state, state.current, ["MAG-S010"])[0]
    ctx = ctx_for(state, source=spell)
    ctx.player.resource = 0
    assert invoke(ctx) == 1


def test_units_get_no_spell_bonus() -> None:
    state = make_game()
    unit = make_cards(state, state.current, ["MAG-S012"])[0]
    ctx = ctx_for(state, source=unit)
    ctx.player.resource = 2
    ctx.answers = [2]
    assert invoke(ctx) == 2
