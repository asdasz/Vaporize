from __future__ import annotations

import pytest

from engine.actions import Attack, EndTurn, IllegalAction, Undo, apply_action
from engine.view import build_view
from tests.helpers import catalog, make_game, place_unit


def _units(state, seat):  # type: ignore[no-untyped-def]
    return {u.uid: u for _, u in state.units_of(seat)}


def test_attack_same_tier_or_one_higher_and_taps() -> None:
    state = make_game()
    seat, enemy = state.current, (state.current + 1) % 2
    me = place_unit(state, seat, 1, def_id="MAG-P044", hp=4)
    me.fixed_attack = 1
    same = place_unit(state, enemy, 1, hp=3)
    higher = place_unit(state, enemy, 2, hp=3)
    too_high = place_unit(state, enemy, 3, hp=3)
    assert set(build_view(state, catalog(), seat)["legal"]["attacks"][me.uid]) == {same.uid, higher.uid}
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, me.uid, too_high.uid))
    assert exc.value.key == "error.out_of_range"
    state, events = apply_action(state, catalog(), Attack(seat, me.uid, higher.uid))
    assert _units(state, enemy)[higher.uid].current_hp == 2
    assert _units(state, seat)[me.uid].tapped
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, me.uid, same.uid))
    assert exc.value.key == "error.unit_tapped"
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert not _units(state, seat)[me.uid].tapped  # untaps at end of its owner's turn


def test_cannot_attack_lower_tier_own_units_or_with_zero_attack_or_stunned() -> None:
    state = make_game()
    seat, enemy = state.current, (state.current + 1) % 2
    me = place_unit(state, seat, 2)
    me.fixed_attack = 2
    lower = place_unit(state, enemy, 1)
    friend = place_unit(state, seat, 2)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, me.uid, lower.uid))
    assert exc.value.key == "error.out_of_range"
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, me.uid, friend.uid))
    assert exc.value.key == "error.invalid_target"
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, friend.uid, lower.uid))  # 0 attack
    assert exc.value.key == "error.no_attack"
    me.status["stun"] = 1
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, me.uid, lower.uid))
    assert exc.value.key == "error.unit_stunned"


def test_attack_kills_and_can_be_undone() -> None:
    state = make_game()
    seat, enemy = state.current, (state.current + 1) % 2
    me = place_unit(state, seat, 1)
    me.fixed_attack = 5
    target = place_unit(state, enemy, 1, hp=2)
    state, _ = apply_action(state, catalog(), Attack(seat, me.uid, target.uid))
    assert state.units_of(enemy) == [] and state.players[enemy].discard.find(target.uid)
    state, _ = apply_action(state, catalog(), Undo(seat))
    assert target.uid in _units(state, enemy) and not _units(state, seat)[me.uid].tapped


def test_shield_absorbs_attack() -> None:
    state = make_game()
    seat, enemy = state.current, (state.current + 1) % 2
    me = place_unit(state, seat, 1)
    me.fixed_attack = 5
    target = place_unit(state, enemy, 1, hp=2)
    target.status["shield"] = 1
    state, _ = apply_action(state, catalog(), Attack(seat, me.uid, target.uid))
    assert _units(state, enemy)[target.uid].current_hp == 2
