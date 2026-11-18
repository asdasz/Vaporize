"""Shared market cards 761-790."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Attack, CancelChoice, Develop, EndTurn, IllegalAction, PlayCard, Respond, apply_action
from engine.state import GameState
from tests.helpers import catalog, make_cards, make_game, place_unit, set_hand


def _setup(hand: list[str], mana: int = 0, players: int = 2) -> tuple[GameState, int, list[str]]:
    state = make_game(players=players)
    seat = state.current
    cards = set_hand(state, seat, hand + ["MAG-S001"] * max(0, 7 - len(hand)))
    state.players[seat].resource = mana
    return state, seat, [c.uid for c in cards]


def _play(state: GameState, seat: int, uid: str, *answers: Any) -> GameState:
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    for answer in answers:
        assert state.pending is not None, "expected a prompt"
        state, _ = apply_action(state, catalog(), Respond(seat, answer))
    assert state.pending is None, f"unexpected prompt {state.pending.prompt.kind if state.pending else ''}"
    return state


def _unit(state: GameState, seat: int, uid: str):  # type: ignore[no-untyped-def]
    return next((u for _, u in state.units_of(seat) if u.uid == uid), None)


def _hand_unit(state: GameState, seat: int, card_id: str) -> str:
    return state.players[seat].tiers[1].cards()[-1].uid


def test_all_30_load() -> None:
    assert set(range(761, 791)) <= {c.number for c in catalog().shared_cards()}


def test_761_boost_and_vp_when_its_attack_kills() -> None:
    state, seat, uids = _setup(["SHR-761"], mana=1)
    mine = place_unit(state, seat, 1)
    target = place_unit(state, (seat + 1) % 2, 1, hp=3)
    state = _play(state, seat, uids[0], 1, mine.uid)  # 1 + 1 (class) + 1 = +3 attack
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, target.uid))
    assert _unit(state, (seat + 1) % 2, target.uid) is None and state.players[seat].vp == 1


def test_762_bounce_enemy_unit_and_random_discard() -> None:
    state, seat, uids = _setup(["SHR-762"])
    enemy = (seat + 1) % 2
    set_hand(state, enemy, ["MAG-S001", "MAG-S002"])
    unit = place_unit(state, enemy, 3)
    state = _play(state, seat, uids[0], unit.uid)
    p = state.players[enemy]
    assert p.hand.find(unit.uid) and len(p.hand) == 2 and len(p.discard) == 1
    assert state.undo_stack == []


def test_763_kill_cheap_unit_of_each_opponent_ignoring_shields() -> None:
    state, seat, uids = _setup(["SHR-763"], players=3)
    cheap = {o: place_unit(state, o, 2) for o in (p.seat for p in state.players if p.seat != seat)}
    pricey = place_unit(state, (seat + 1) % 3, 1, def_id="SHR-790")  # cost 8
    for u in cheap.values():
        u.status["shield"] = 2
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert pricey.uid not in state.pending.prompt.options
    for o, u in cheap.items():
        state, _ = apply_action(state, catalog(), Respond(seat, u.uid))
    assert all(_unit(state, o, u.uid) is None for o, u in cheap.items())


def test_764_draw_3_and_others_draw_1() -> None:
    state, seat, uids = _setup(["SHR-764"])
    other = (seat + 1) % 2
    mine, theirs = len(state.players[seat].hand), len(state.players[other].hand)
    state = _play(state, seat, uids[0])
    assert len(state.players[seat].hand) == mine - 1 + 3 and len(state.players[other].hand) == theirs + 1


def test_765_shield_up_to_invoke_units_and_vp_after_3_water() -> None:
    state, seat, uids = _setup(["MAG-S006", "MAG-S007", "MAG-S012", "SHR-765"], mana=1)
    a, b = place_unit(state, seat, 1), place_unit(state, seat, 2)
    for uid in uids[:3]:
        state = _play(state, seat, uid)
    state = _play(state, seat, uids[3], 1, [a.uid, b.uid])  # value 1 + 1 = 2 units
    assert _unit(state, seat, a.uid).status["shield"] == 1 and _unit(state, seat, b.uid).status["shield"] == 1
    assert state.players[seat].vp == 1


def test_766_vp_per_tier_and_inf_with_4_water() -> None:
    state, seat, uids = _setup(["SHR-766"])
    for tier in (1, 2, 4):
        place_unit(state, seat, tier)
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S006"] * 3)  # + 766 itself = 4
    state = _play(state, seat, uids[0])
    assert (state.players[seat].vp, state.players[seat].inf) == (3, 1)


def test_767_deal_2_damage_invoke_times() -> None:
    state, seat, uids = _setup(["SHR-767"], mana=1)
    target = place_unit(state, (seat + 1) % 2, 1, hp=9)
    target.status["shield"] = 1
    state = _play(state, seat, uids[0], 1, target.uid, target.uid)  # 2 hits, the first absorbed
    assert _unit(state, (seat + 1) % 2, target.uid).current_hp == 7


def test_768_vp_equal_to_invoke_max_3() -> None:
    state, seat, uids = _setup(["SHR-768"], mana=4)
    assert _play(state, seat, uids[0], 4).players[seat].vp == 3


def test_769_resolve_a_market_card_then_discard_it() -> None:
    state, seat, uids = _setup(["SHR-769"])
    copied = make_cards(state, -1, ["SHR-733"])[0]  # gain 3 inf and prepare
    state.shared_market.row.slots[0] = copied
    state = _play(state, seat, uids[0], copied.uid)
    assert (state.players[seat].inf, state.players[seat].resource) == (3, 1)
    assert state.shared_market.removed.find(copied.uid) and state.shared_market.row.slots[0].uid != copied.uid


def test_770_damage_all_or_pay_3_to_spare_yours() -> None:
    state, seat, uids = _setup(["SHR-770"], mana=2)
    mine, theirs = place_unit(state, seat, 1, hp=9), place_unit(state, (seat + 1) % 2, 1, hp=9)
    hit_all = _play(state, seat, uids[0], 1, 2)  # value 3 -> ceil(3/2)+1 = 3
    assert _unit(hit_all, seat, mine.uid).current_hp == 6 and _unit(hit_all, (seat + 1) % 2, theirs.uid).current_hp == 6
    with pytest.raises(IllegalAction):
        _play(state, seat, uids[0], 0, 2)  # can't pay 3 inf
    state.players[seat].inf = 3
    spared = _play(state, seat, uids[0], 0, 2)
    assert _unit(spared, seat, mine.uid).current_hp == 9 and spared.players[seat].inf == 0


def test_771_split_double_invoke_vp_on_kill_and_stun_harmed() -> None:
    hand = ["MAG-S001", "MAG-S002", "MAG-S005", "MAG-S005", "SHR-771"]
    state, seat, uids = _setup(hand, mana=1)
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S001"] * 2)
    weak, tough = place_unit(state, (seat + 1) % 2, 1, hp=1), place_unit(state, (seat + 1) % 2, 2, hp=9)
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    state = _play(state, seat, uids[4], 1, {weak.uid: 1, tough.uid: 3})  # (1+1)*2 = 4
    assert _unit(state, (seat + 1) % 2, weak.uid) is None and state.players[seat].vp == 1
    assert _unit(state, (seat + 1) % 2, tough.uid).status["stun"] == 1


def test_772_kill_all_units_on_a_tier() -> None:
    state, seat, uids = _setup(["SHR-772"])
    a, b, c = place_unit(state, seat, 2), place_unit(state, (seat + 1) % 2, 2), place_unit(state, (seat + 1) % 2, 1)
    state = _play(state, seat, uids[0], 2)
    assert _unit(state, seat, a.uid) is None and _unit(state, (seat + 1) % 2, b.uid) is None
    assert _unit(state, (seat + 1) % 2, c.uid) is not None


def test_773_sacrifice_for_hp_and_tier_minus_one_vp() -> None:
    state, seat, uids = _setup(["SHR-773"])
    victim = place_unit(state, seat, 3, hp=4)
    state = _play(state, seat, uids[0], victim.uid)
    unit = state.players[seat].tiers[1].cards()[0]
    assert unit.current_hp == 3 + 4 and state.players[seat].vp == 2 and _unit(state, seat, victim.uid) is None


def test_774_degrade_with_10_cards_in_discard() -> None:
    state, seat, uids = _setup(["SHR-774"])
    target = place_unit(state, (seat + 1) % 2, 2)
    assert _play(state, seat, uids[0]) is not None  # 1 card in discard: nothing
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S001"] * 10)  # units go to the board, not the pile
    state = _play(state, seat, uids[0], target.uid)
    assert state.players[(seat + 1) % 2].tiers[1].find(target.uid)


def test_775_sot_prepare_776_vanilla_invoke_hp() -> None:
    state, seat, uids = _setup(["SHR-776"], mana=2)
    state = _play(state, seat, uids[0], 2)
    assert state.players[seat].tiers[1].cards()[0].current_hp == 3
    unit = place_unit(state, seat, 2, def_id="SHR-775")
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    state, _ = apply_action(state, catalog(), EndTurn(state.current))
    assert state.players[seat].resource == 4  # 0 -> +3 (class) +1 (775 prepare)
    assert _unit(state, seat, unit.uid) is not None


def test_777_prepares_when_played() -> None:
    state, seat, uids = _setup(["SHR-777"])
    assert _play(state, seat, uids[0]).players[seat].resource == 1


def test_778_damages_its_attackers() -> None:
    state, seat, uids = _setup([])
    guard = place_unit(state, (seat + 1) % 2, 1, def_id="SHR-778", hp=5)
    attacker = place_unit(state, seat, 1, hp=2)
    attacker.fixed_attack = 1
    state, _ = apply_action(state, catalog(), Attack(seat, attacker.uid, guard.uid))
    assert _unit(state, seat, attacker.uid).current_hp == 1


def test_779_prepare_x2_before_hp() -> None:
    state, seat, uids = _setup(["SHR-779"])
    state = _play(state, seat, uids[0], 2)  # mana 0 -> 2 by prepares, spend 2 -> HP 2
    assert state.players[seat].tiers[1].cards()[0].current_hp == 2
    state, seat, uids = _setup(["SHR-779"])
    state = _play(state, seat, uids[0], 0)
    assert state.players[seat].tiers[1].cards()[0].current_hp == 1  # min. 1


def test_781_bonus_attack_any_tier_after_2_wind() -> None:
    state, seat, uids = _setup(["MAG-S008", "MAG-S008", "SHR-781"])
    far = place_unit(state, (seat + 1) % 2, 4, hp=9)
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])
    state = _play(state, seat, uids[2])
    unit = state.players[seat].tiers[1].cards()[0]
    state, _ = apply_action(state, catalog(), Attack(seat, unit.uid, far.uid))  # tier 1 -> tier 4
    assert _unit(state, (seat + 1) % 2, far.uid).current_hp == 9 - 4


def test_782_eot_prompt_invoke_damage_after_2_fire() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002"], mana=2)
    place_unit(state, seat, 1, def_id="SHR-782", hp=4)
    target = place_unit(state, (seat + 1) % 2, 1, hp=5)
    for uid in uids[:2]:
        state = _play(state, seat, uid)
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.pending is not None and state.pending.kind == "end_turn" and state.current == seat
    state, _ = apply_action(state, catalog(), Respond(seat, 2))  # invoke before the Mage loses mana at EOT
    state, _ = apply_action(state, catalog(), Respond(seat, target.uid))
    assert state.pending is None and state.current != seat
    assert _unit(state, (seat + 1) % 2, target.uid).current_hp == 3


def test_782_end_turn_prompt_can_be_cancelled() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002"], mana=1)
    place_unit(state, seat, 1, def_id="SHR-782")
    for uid in uids[:2]:
        state = _play(state, seat, uid)
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    state, _ = apply_action(state, catalog(), CancelChoice(seat))
    assert state.pending is None and state.current == seat


def test_784_and_788_attack_twice_and_788_stuns() -> None:
    state, seat, uids = _setup([])
    twin = place_unit(state, seat, 1, def_id="SHR-784")
    twin.fixed_attack = 2
    lancer = place_unit(state, seat, 1, def_id="SHR-788")
    lancer.fixed_attack = 1
    target = place_unit(state, (seat + 1) % 2, 1, hp=20)
    for attacker in (twin, twin, lancer, lancer):
        state, _ = apply_action(state, catalog(), Attack(seat, attacker.uid, target.uid))
    t = _unit(state, (seat + 1) % 2, target.uid)
    assert t.current_hp == 20 - 6 and t.status["stun"] == 2


def test_785_hp_invoke_x2_and_sot_inf() -> None:
    state, seat, uids = _setup(["SHR-785"], mana=3)
    state = _play(state, seat, uids[0], 3)
    assert state.players[seat].tiers[1].cards()[0].current_hp == 6
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    state, _ = apply_action(state, catalog(), EndTurn(state.current))
    assert state.players[seat].inf == 1


def test_786_takes_at_most_2_per_hit() -> None:
    state, seat, uids = _setup(["SHR-750"])
    shell = place_unit(state, (seat + 1) % 2, 1, def_id="SHR-786", hp=5)
    attacker = place_unit(state, seat, 1)
    attacker.fixed_attack = 9
    state, _ = apply_action(state, catalog(), Attack(seat, attacker.uid, shell.uid))
    assert _unit(state, (seat + 1) % 2, shell.uid).current_hp == 3


def test_787_damages_its_new_tier_when_developed() -> None:
    state, seat, uids = _setup([])
    titan = place_unit(state, seat, 1, def_id="SHR-787", hp=4)
    other = place_unit(state, (seat + 1) % 2, 2, hp=5)
    state.players[seat].inf = 3
    state, _ = apply_action(state, catalog(), Develop(seat, titan.uid))
    assert _unit(state, (seat + 1) % 2, other.uid).current_hp == 3 and _unit(state, seat, titan.uid).current_hp == 4


def test_789_prepare_before_each_invoke() -> None:
    state, seat, uids = _setup(["MAG-S010"], mana=3)
    place_unit(state, seat, 1, def_id="SHR-789")
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert state.pending.prompt.max == 4  # prepared first: 3 -> 4


def test_790_and_783_vanilla_invoke_hp() -> None:
    for card, bonus in (("SHR-790", 5), ("SHR-783", 2), ("SHR-780", None)):
        state, seat, uids = _setup([card], mana=1)
        state = _play(state, seat, uids[0], *(1,) if bonus is not None else ())
        unit = state.players[seat].tiers[1].cards()[0]
        assert unit.current_hp == (1 + bonus if bonus is not None else 4)
