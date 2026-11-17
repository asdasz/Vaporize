from __future__ import annotations

import pytest

from engine.effects.registry import get_effect
from engine.prompts import NeedChoice
from tests.helpers import ctx_for, make_game, place_unit

ANY_1_3 = {"side": "any", "tiers": [1, 2, 3]}


def test_deal_damage_asks_for_a_target() -> None:
    state = make_game()
    enemy = (state.current + 1) % 2
    unit = place_unit(state, enemy, 2, hp=3)
    with pytest.raises(NeedChoice) as need:
        get_effect("deal_damage").fn(ctx_for(state), {"amount": 2, "target": ANY_1_3})
    assert need.value.prompt.kind == "choose_unit"
    assert unit.uid in need.value.prompt.options


def test_deal_damage_reduces_hp() -> None:
    state = make_game()
    unit = place_unit(state, (state.current + 1) % 2, 2, hp=3)
    ctx = ctx_for(state)
    ctx.answers = [unit.uid]
    get_effect("deal_damage").fn(ctx, {"amount": 2, "target": ANY_1_3})
    assert unit.current_hp == 1


def test_lethal_damage_sends_unit_to_owners_discard() -> None:
    state = make_game()
    enemy = (state.current + 1) % 2
    unit = place_unit(state, enemy, 1, hp=2)
    ctx = ctx_for(state)
    ctx.answers = [unit.uid]
    get_effect("deal_damage").fn(ctx, {"amount": 5, "target": ANY_1_3})
    assert state.players[enemy].tiers[1].cards() == []
    assert state.players[enemy].discard.find(unit.uid) is not None
    assert unit.current_hp is None  # runtime state reset


def test_destroyed_token_is_removed_from_game() -> None:
    state = make_game()
    enemy = (state.current + 1) % 2
    token = place_unit(state, enemy, 1, hp=1)
    state.players[enemy].tiers[1].take(token.uid)
    token.is_token = True
    state.players[enemy].tokens.put_bottom(token)
    ctx = ctx_for(state)
    ctx.answers = [token.uid]
    get_effect("deal_damage").fn(ctx, {"amount": 1, "target": ANY_1_3})
    assert state.players[enemy].tokens.is_empty()
    assert state.players[enemy].discard.find(token.uid) is None


def test_shield_absorbs_a_whole_hit() -> None:
    state = make_game()
    unit = place_unit(state, (state.current + 1) % 2, 1, hp=2)
    unit.status["shield"] = 1
    ctx = ctx_for(state)
    ctx.answers = [unit.uid]
    get_effect("deal_damage").fn(ctx, {"amount": 9, "target": ANY_1_3})
    assert unit.current_hp == 2 and unit.status["shield"] == 0


def test_target_tiers_are_respected() -> None:
    state = make_game()
    place_unit(state, (state.current + 1) % 2, 4)
    ctx = ctx_for(state)
    get_effect("deal_damage").fn(ctx, {"amount": 2, "target": ANY_1_3})  # no valid target: nothing happens
    assert ctx.events == []


def test_split_damage_on_one_tier() -> None:
    state = make_game()
    enemy = (state.current + 1) % 2
    a = place_unit(state, enemy, 2, hp=3)
    b = place_unit(state, state.current, 2, hp=3)
    ctx = ctx_for(state)
    ctx.keywords["split"] = {"scope": "same_tier"}
    ctx.answers = [{a.uid: 2, b.uid: 1}]
    get_effect("deal_damage").fn(ctx, {"amount": 3, "target": ANY_1_3})
    assert (a.current_hp, b.current_hp) == (1, 2)


def test_heal_respects_max_hp_but_never_lowers() -> None:
    state = make_game()
    seat = state.current
    low = place_unit(state, seat, 1, hp=4)
    high = place_unit(state, seat, 2, hp=8)
    for unit, expected in ((low, 6), (high, 8)):
        ctx = ctx_for(state)
        ctx.answers = [unit.uid]
        get_effect("heal").fn(ctx, {"amount": 5, "target": {"side": "ally"}, "max_hp": 6})
        assert unit.current_hp == expected


def test_heal_only_targets_allies() -> None:
    state = make_game()
    enemy_unit = place_unit(state, (state.current + 1) % 2, 1)
    ctx = ctx_for(state)
    ctx.answers = [enemy_unit.uid]
    get_effect("heal").fn(ctx, {"amount": 2, "target": {"side": "ally"}})  # no ally units: no prompt
    assert enemy_unit.current_hp == 2
