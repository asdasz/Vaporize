"""Monarch class board (gold, tax, passives) and its cards 101-112, 131-145."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Attack, Bank, Buy, Develop, EndTurn, IllegalAction, PlayCard, Respond, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_game, place_unit, set_hand

FILLER = ["MON-S101"] * 6


def _setup(hand: list[str], gold: int = 0, opponent: str = "monarch") -> tuple[GameState, int, list[str]]:
    state = make_game(classes=["monarch", opponent])
    if state.current != 0:  # the Monarch (seat 0) goes first in these tests
        state = make_game(classes=["monarch", opponent], seed=2)
    assert state.current == 0
    cards = set_hand(state, 0, hand + FILLER[: max(0, 7 - len(hand))])
    state.players[0].resource = gold
    return state, 0, [c.uid for c in cards]


def _do(state: GameState, action: Any, *answers: Any) -> GameState:
    state, _ = apply_action(state, catalog(), action)
    for answer in answers:
        assert state.pending is not None, "expected a prompt"
        state, _ = apply_action(state, catalog(), Respond(action.seat, answer))
    assert state.pending is None, f"unexpected prompt {state.pending.prompt.kind if state.pending else ''}"
    return state


def _play(state: GameState, seat: int, uid: str, *answers: Any) -> GameState:
    return _do(state, PlayCard(seat, uid), *answers)


def _end(state: GameState, seat: int = 0) -> GameState:
    return _do(state, EndTurn(seat))


# --- class board -------------------------------------------------------------------------------


def test_board() -> None:
    cdef = catalog().cls("monarch")
    assert cdef.primary_elements == ("water", "wind")
    assert cdef.resource.key == "gold" and cdef.resource.start == 0 and cdef.resource.hard_max == 20
    assert [cdef.tiers[t].spots for t in (1, 2, 3)] == [2, 2, 3]
    assert [cdef.tiers[t].develop_cost for t in (2, 3, 4)] == [3, 4, 5]
    assert len(catalog().starter_cards("monarch")) == 12
    assert [c.number for c in catalog().private_cards("monarch")] == list(range(131, 146))


@pytest.mark.parametrize(("gold", "left"), [(3, 3), (4, 3), (7, 6), (8, 6), (13, 10), (20, 15)])
def test_tax_pays_one_per_four_gold(gold: int, left: int) -> None:
    state, _, _ = _setup([], gold=gold)
    state = _end(state)
    assert state.players[0].resource == left


def test_gold_is_kept_between_turns() -> None:
    state, _, _ = _setup([], gold=2)
    state = _end(state)
    state = _do(state, EndTurn(1))
    assert state.players[0].resource == 2


def test_prepare_gains_two_gold_up_to_twenty() -> None:
    state, seat, uids = _setup(["MON-S109"], gold=19)
    state = _play(state, seat, uids[0])
    assert state.players[seat].resource == 20


def test_invoke_spends_up_to_ten_gold() -> None:
    state, seat, uids = _setup(["MON-S111"], gold=14)
    enemy = place_unit(state, 1, 1, hp=20)
    place_unit(state, 0, 1)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert state.pending.prompt.kind == "number" and state.pending.prompt.max == 10
    state = _do(state, Respond(seat, 10), enemy.uid)
    assert state.players[seat].resource == 4
    assert next(u for _, u in state.units_of(1)).current_hp == 20 - 11


def test_units_enter_with_one_more_hp() -> None:
    state, seat, uids = _setup(["MON-S112"], gold=4)
    state = _play(state, seat, uids[0], 4)  # invoke 4 -> 3 HP, +1 Monarch
    unit = state.players[seat].tiers[1].cards()[0]
    assert (unit.fixed_attack, unit.current_hp) == (1, 4)


def test_any_tier_attack_once_per_turn() -> None:
    state, _, _ = _setup([], opponent="mage")
    attackers = [place_unit(state, 0, 1, "MON-S112"), place_unit(state, 0, 1, "MON-S112")]
    for a in attackers:
        a.fixed_attack = 1
    far = [place_unit(state, 1, 3, hp=5), place_unit(state, 1, 4, hp=5)]  # the Mage has 1 spot on T3
    view = build_view(state, catalog(), 0)
    assert far[0].uid in view["legal"]["attacks"][attackers[0].uid]
    state = _do(state, Attack(0, attackers[0].uid, far[0].uid))
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Attack(0, attackers[1].uid, far[1].uid))  # used up this turn


def test_normal_range_attack_keeps_the_any_tier_attack() -> None:
    state, _, _ = _setup([], opponent="mage")
    a, b = place_unit(state, 0, 1, "MON-S112"), place_unit(state, 0, 1, "MON-S112")
    a.fixed_attack = b.fixed_attack = 1
    near, far = place_unit(state, 1, 2, hp=5), place_unit(state, 1, 3, hp=5)
    state = _do(state, Attack(0, a.uid, near.uid))
    state = _do(state, Attack(0, b.uid, far.uid))
    assert state.players[0].any_tier_attacks == 0


def test_mage_has_no_any_tier_attack() -> None:
    state = make_game()
    seat = state.current
    unit = place_unit(state, seat, 1)
    unit.fixed_attack = 1
    far = place_unit(state, 1 - seat, 3)
    assert far.uid not in build_view(state, catalog(), seat)["legal"]["attacks"].get(unit.uid, [])


def test_view_shows_tax_preview() -> None:
    state, _, _ = _setup([], gold=9)
    assert build_view(state, catalog(), 1)["players"][0]["tax"] == 2


# --- starter cards ------------------------------------------------------------------------------


def test_starter_influences() -> None:
    state, seat, uids = _setup(["MON-S101", "MON-S107"])
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])
    assert state.players[seat].inf == 2


def test_111_targets_own_tiers_and_one_above() -> None:
    state, seat, uids = _setup(["MON-S111"], gold=1)
    place_unit(state, 0, 1)
    t2, t3 = place_unit(state, 1, 2, hp=5), place_unit(state, 1, 3, hp=5)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    state, _ = apply_action(state, catalog(), Respond(seat, 1))
    assert t2.uid in state.pending.prompt.options and t3.uid not in state.pending.prompt.options
    state = _do(state, Respond(seat, t2.uid))
    assert next(u for t, u in state.units_of(1) if t == 2).current_hp == 5 - 2


def test_112_health_is_invoke_minus_one_at_least_one() -> None:
    state, seat, uids = _setup(["MON-S112"])
    state = _play(state, seat, uids[0])  # no gold: invoke 0 -> 1 HP, +1
    assert state.players[seat].tiers[1].cards()[0].current_hp == 2


# --- market cards -------------------------------------------------------------------------------


def test_131_prepares_after_two_water() -> None:
    state, seat, uids = _setup(["MON-S101", "MON-S102", "MON-P131"])
    for uid in uids[:3]:
        state = _play(state, seat, uid)
    assert (state.players[seat].inf, state.players[seat].resource) == (4, 2)


def test_132_inf_only_for_developing() -> None:
    state, seat, uids = _setup(["MON-P132"])
    unit = place_unit(state, 0, 1)
    state = _play(state, seat, uids[0])
    p = state.players[seat]
    assert (p.inf, p.develop_inf) == (0, 3)
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Buy(seat, "basic", 0))
    state = _do(state, Develop(seat, unit.uid))
    assert state.players[seat].develop_inf == 0
    state = _end(state)
    assert state.players[0].develop_inf == 0


def test_132_develop_inf_is_used_first_then_inf() -> None:
    state, seat, uids = _setup(["MON-P132", "MON-S101"])
    unit = place_unit(state, 0, 2)
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])
    state = _do(state, Develop(seat, unit.uid))  # T3 costs 4: 3 develop-only + 1 inf
    p = state.players[seat]
    assert (p.develop_inf, p.inf) == (0, 0)


def test_133_unspent_inf_becomes_gold_before_tax() -> None:
    state, seat, uids = _setup(["MON-P133", "MON-S101"], gold=1)
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])
    state = _end(state)
    assert state.players[0].resource == 1 + 4 - 1  # 5 gold, tax 1


def test_134_invoke_does_not_spend_gold_max_8() -> None:
    state, seat, uids = _setup(["MON-P134"], gold=10)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert state.pending.prompt.max == 8 and state.pending.prompt.params.get("free")
    state = _do(state, Respond(seat, 8))
    p = state.players[seat]
    assert (p.inf, p.resource) == (8, 10)


def test_135_no_tax_this_turn() -> None:
    state, seat, uids = _setup(["MON-P135"], gold=12)
    state = _play(state, seat, uids[0])
    state = _end(state)
    assert state.players[0].resource == 12


def test_136_bonuses() -> None:
    state, seat, uids = _setup(["MON-S107", "MON-S108", "MON-S101", "MON-S102", "MON-P136"])
    for uid in uids[:5]:
        state = _play(state, seat, uid)
    p = state.players[seat]
    assert (p.inf, p.resource) == (4 + 4 + 2, 4)


def test_137_gold_when_another_player_buys() -> None:
    state, _, _ = _setup([])
    place_unit(state, 1, 1, "MON-P137")
    state.players[0].inf = 10
    state = _do(state, Buy(0, "basic", 0))
    assert state.players[1].resource == 1
    place_unit(state, 0, 1, "MON-P137")
    state = _do(state, Buy(0, "basic", 0))
    assert (state.players[0].resource, state.players[1].resource) == (0, 2)  # your own buys don't count


def test_138_vp_per_four_gold() -> None:
    state, seat, uids = _setup(["MON-P138"], gold=9)
    state = _play(state, seat, uids[0])
    assert state.players[seat].vp == 1 + 2


def test_139_pay_gold_per_damage_and_inf_on_kill() -> None:
    state, seat, uids = _setup(["MON-P139"], gold=3)
    target = place_unit(state, 1, 2, hp=2)
    other = place_unit(state, 1, 1, hp=5)
    state = _play(state, seat, uids[0], target.uid, target.uid, other.uid)  # 3 gold: kill (2) + 1 dmg; out of gold
    p = state.players[seat]
    assert (p.resource, p.inf) == (0, 1)
    assert next(u for _, u in state.units_of(1)).current_hp == 4


def test_139_stop_early() -> None:
    state, seat, uids = _setup(["MON-P139"], gold=3)
    target = place_unit(state, 1, 2, hp=5)
    state = _play(state, seat, uids[0], target.uid, None)
    assert (state.players[seat].resource, state.players[seat].inf) == (2, 0)


def test_140_vp_per_unit() -> None:
    state, seat, uids = _setup(["MON-P140"])
    place_unit(state, 0, 1)
    place_unit(state, 0, 2)
    state = _play(state, seat, uids[0])
    assert state.players[seat].vp == 3


def test_141_gold_per_unit_on_its_tier_all_players_before_tax() -> None:
    state, _, _ = _setup([], gold=1)
    place_unit(state, 0, 2, "MON-P141")
    place_unit(state, 0, 1)  # other tiers don't count
    place_unit(state, 1, 2)
    place_unit(state, 1, 2)  # other players' units on that tier count too
    state = _end(state)
    assert state.players[0].resource == 1 + 3 - 1  # 4 gold -> tax 1


def test_141_counts_three_opponents_example() -> None:
    """Jan's example: P1 has 1 unit on T1, P2 has 2, I (P3) have 141 there -> 4 gold."""
    state = make_game(players=3, classes=["mage", "mage", "monarch"])
    me = 2
    place_unit(state, 0, 1)
    place_unit(state, 1, 1)
    place_unit(state, 1, 1)
    place_unit(state, me, 1, "MON-P141")
    from engine.context import EffectContext
    from engine.values import resolve_value

    unit = next(u for _, u in state.units_of(me))
    ctx = EffectContext(state, catalog(), me, unit, [])
    assert resolve_value(ctx, {"count": {"units_on_source_tier": {}}}) == 4


def test_142_pay_gold_for_attack_when_attacking() -> None:
    state, _, _ = _setup([], gold=5, opponent="mage")
    champ = place_unit(state, 0, 1, "MON-P142")
    champ.fixed_attack = 1
    target = place_unit(state, 1, 1, hp=9)
    state, _ = apply_action(state, catalog(), Attack(0, champ.uid, target.uid))
    assert state.pending.kind == "attack" and state.pending.prompt.max == 2
    state = _do(state, Respond(0, 2))
    assert state.players[0].resource == 1
    assert next(u for _, u in state.units_of(1)).current_hp == 9 - 5


def test_142_no_prompt_without_gold() -> None:
    state, _, _ = _setup([], gold=1, opponent="mage")
    champ = place_unit(state, 0, 1, "MON-P142")
    champ.fixed_attack = 1
    target = place_unit(state, 1, 1, hp=9)
    state = _do(state, Attack(0, champ.uid, target.uid))
    assert next(u for _, u in state.units_of(1)).current_hp == 8


def test_143_bank_doubles_and_is_not_taxed() -> None:
    state, _, _ = _setup([], gold=8)
    vault = place_unit(state, 0, 1, "MON-P143")
    state = _do(state, Bank(0, vault.uid, 5))
    assert state.players[0].resource == 3
    state = _end(state)  # 3 gold: no tax; 5 on the vault -> 10
    assert state.players[0].resource == 3
    assert next(u for _, u in state.units_of(0)).stored == 10
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Bank(0, vault.uid, -1))  # not your turn
    state = _do(state, EndTurn(1))
    state = _do(state, Bank(0, vault.uid, -10))
    assert state.players[0].resource == 13


def test_143_take_is_limited_by_the_gold_cap() -> None:
    state, _, _ = _setup([], gold=18)
    vault = place_unit(state, 0, 1, "MON-P143")
    vault.stored = 10
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Bank(0, vault.uid, -3))
    assert build_view(state, catalog(), 0)["legal"]["bank"][vault.uid]["take"] == 2


def test_143_gold_is_lost_when_it_dies() -> None:
    state, seat, uids = _setup(["MON-P139"], gold=1)
    vault = place_unit(state, 1, 1, "MON-P143", hp=1)
    vault.stored = 6
    state = _play(state, seat, uids[0], vault.uid)
    dead = next(c for c in state.players[1].discard if c.def_id == "MON-P143")
    assert dead.stored == 0


def test_144_vp_per_tax() -> None:
    state, _, _ = _setup([], gold=8)
    place_unit(state, 0, 1, "MON-P144")
    state = _end(state)
    assert (state.players[0].resource, state.players[0].vp) == (6, 2)


def test_145_develop_with_gold() -> None:
    state, _, _ = _setup([], gold=3)
    knight = place_unit(state, 0, 1, "MON-P145")
    view = build_view(state, catalog(), 0)
    assert view["legal"]["develop_resource"][knight.uid] == {"cost": 3, "to": 2}
    assert knight.uid not in view["legal"]["develop"]
    state = _do(state, Develop(0, knight.uid, pay="resource"))
    assert state.players[0].resource == 0
    other = place_unit(state, 0, 1)
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Develop(0, other.uid, pay="resource"))
