from __future__ import annotations

import pytest

from engine.actions import Develop, EndTurn, IllegalAction, PlayCard, Undo, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_game, place_unit, set_hand


def _develop(state: GameState, seat: int, uid: str) -> GameState:
    return apply_action(state, catalog(), Develop(seat, uid))[0]


def _tier_of(state: GameState, seat: int, uid: str) -> int:
    return next(t for t, u in state.units_of(seat) if u.uid == uid)


def test_develop_costs_3_4_5_and_moves_one_tier_at_a_time() -> None:
    state = make_game(players=2)
    seat = state.current
    unit = place_unit(state, seat, 1)
    state.players[seat].inf = 12
    for tier, inf_left in ((2, 9), (3, 5), (4, 0)):
        state = _develop(state, seat, unit.uid)
        assert _tier_of(state, seat, unit.uid) == tier
        assert state.players[seat].inf == inf_left
    assert state.tier4.find(unit.uid) is not None
    assert state.players[seat].tiers[3].cards() == []


def test_develop_requires_enough_inf() -> None:
    state = make_game()
    seat = state.current
    unit = place_unit(state, seat, 1)
    state.players[seat].inf = 2
    with pytest.raises(IllegalAction) as exc:
        _develop(state, seat, unit.uid)
    assert exc.value.key == "error.not_enough_inf" and exc.value.params == {"cost": 3}


def test_develop_requires_a_free_spot() -> None:
    state = make_game()
    seat = state.current
    place_unit(state, seat, 3)  # Mage tier 3 has 1 spot
    unit = place_unit(state, seat, 2)
    state.players[seat].inf = 10
    with pytest.raises(IllegalAction) as exc:
        _develop(state, seat, unit.uid)
    assert exc.value.key == "error.tier_full" and exc.value.params == {"tier": 3}


def test_tier4_is_shared_first_come_first_served() -> None:
    state = make_game(players=2)  # 1 shared spot
    seat, other = state.current, (state.current + 1) % 2
    place_unit(state, other, 4)
    unit = place_unit(state, seat, 3)
    state.players[seat].inf = 10
    with pytest.raises(IllegalAction) as exc:
        _develop(state, seat, unit.uid)
    assert exc.value.key == "error.tier_full" and exc.value.params == {"tier": 4}


def test_cannot_develop_past_tier4_frozen_or_enemy_units() -> None:
    state = make_game(players=3)
    seat = state.current
    state.players[seat].inf = 10
    top = place_unit(state, seat, 4)
    frozen = place_unit(state, seat, 1)
    frozen.status["freeze"] = 1
    enemy = place_unit(state, (seat + 1) % 3, 1)
    for uid, key in ((top.uid, "error.max_tier"), (frozen.uid, "error.unit_frozen"), (enemy.uid, "error.not_your_unit")):
        with pytest.raises(IllegalAction) as exc:
            _develop(state, seat, uid)
        assert exc.value.key == key


def test_develop_does_not_heal_or_untap() -> None:
    state = make_game()
    seat = state.current
    unit = place_unit(state, seat, 1, hp=1)
    unit.tapped = True
    state.players[seat].inf = 3
    state = _develop(state, seat, unit.uid)
    moved = next(u for _, u in state.units_of(seat) if u.uid == unit.uid)
    assert moved.current_hp == 1 and moved.tapped is True


def test_develop_only_on_your_turn() -> None:
    state = make_game()
    other = (state.current + 1) % 2
    unit = place_unit(state, other, 1)
    state.players[other].inf = 5
    with pytest.raises(IllegalAction) as exc:
        _develop(state, other, unit.uid)
    assert exc.value.key == "error.not_your_turn"


def test_develop_can_be_undone() -> None:
    state = make_game()
    seat = state.current
    unit = place_unit(state, seat, 1)
    state.players[seat].inf = 3
    state = _develop(state, seat, unit.uid)
    state, events = apply_action(state, catalog(), Undo(seat))
    assert _tier_of(state, seat, unit.uid) == 1 and state.players[seat].inf == 3
    assert events[0].params["card"] == "MAG-S012"


def test_play_inf_then_develop_then_score_at_end_of_turn() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S012", "MAG-S001", "MAG-S002", "MAG-S003", "MAG-S004", "MAG-S005", "MAG-S006"])
    for card in cards[:4]:  # unit + 3 inf
        state, _ = apply_action(state, catalog(), PlayCard(seat, card.uid))
    unit_uid = cards[0].uid
    state = _develop(state, seat, unit_uid)
    assert build_view(state, catalog(), seat)["players"][seat]["eot_vp"] == 1
    state, events = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 1
    assert any(e.key == "log.vp_scored" and e.params["amount"] == 1 for e in events)


def test_scoring_by_tier() -> None:
    state = make_game(players=3)
    seat = state.current
    for tier in (1, 2, 2, 3, 4):
        place_unit(state, seat, tier)
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 0 + 1 + 1 + 2 + 3


def test_token_develops_and_scores() -> None:
    state = make_game(players=2)
    seat = state.current
    token = place_unit(state, seat, 1)
    state.players[seat].tiers[1].take(token.uid)
    token.is_token = True
    state.players[seat].tokens.put_bottom(token)
    state.players[seat].inf = 3
    state = _develop(state, seat, token.uid)
    assert state.players[seat].tokens.is_empty()
    assert state.players[seat].tiers[2].find(token.uid) is not None
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 1


def test_view_lists_legal_develops() -> None:
    state = make_game()
    seat = state.current
    cheap = place_unit(state, seat, 1)
    pricey = place_unit(state, seat, 2)
    state.players[seat].inf = 3
    develop = build_view(state, catalog(), seat)["legal"]["develop"]
    assert develop == {cheap.uid: {"cost": 3, "to": 2}}
    assert pricey.uid not in develop
    assert build_view(state, catalog(), (seat + 1) % 2)["legal"]["develop"] == {}
