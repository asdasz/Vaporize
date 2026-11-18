"""Shared market cards 791-811 (there is no 800)."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Attack, Develop, EndTurn, IllegalAction, PlayCard, RemoveCard, Respond, apply_action
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


def _attacker(state: GameState, seat: int, attack: int, tier: int = 1):  # type: ignore[no-untyped-def]
    unit = place_unit(state, seat, tier, hp=9)
    unit.fixed_attack = attack
    return unit


def test_all_load_and_no_800() -> None:
    numbers = {c.number for c in catalog().shared_cards()}
    assert set(range(791, 800)) | set(range(801, 812)) <= numbers and 800 not in numbers


def test_791_vp_when_it_survives_damage() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    tide = place_unit(state, enemy, 1, def_id="SHR-791", hp=5)
    a = _attacker(state, seat, 2)
    state, _ = apply_action(state, catalog(), Attack(seat, a.uid, tide.uid))
    assert state.players[enemy].vp == 1


def test_792_eot_vp_more_on_tier_4() -> None:
    state, seat, _ = _setup([])
    place_unit(state, seat, 4, def_id="SHR-792")
    place_unit(state, seat, 1, def_id="SHR-792")
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 2 + 1 + 3  # abilities + tier 4 scoring


def test_793_survives_lethal_damage_with_2_shadow_in_discard() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    shade = place_unit(state, enemy, 1, def_id="SHR-793", hp=4)
    state.players[enemy].discard.cards = make_cards(state, enemy, ["SHR-772", "SHR-780"])
    deck = len(state.players[enemy].deck)
    a = _attacker(state, seat, 9)
    state, _ = apply_action(state, catalog(), Attack(seat, a.uid, shade.uid))
    assert _unit(state, enemy, shade.uid).current_hp == 1
    assert len(state.players[enemy].discard) == 1 and len(state.players[enemy].deck) == deck + 1


def test_794_hp_per_5_vp() -> None:
    state, seat, uids = _setup(["SHR-794"])
    state.players[seat].vp = 11
    assert _play(state, seat, uids[0]).players[seat].tiers[1].cards()[0].current_hp == 4 + 2


def test_795_shuffled_into_deck_when_it_dies() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    phoenix = place_unit(state, enemy, 1, def_id="SHR-795", hp=4)
    deck = len(state.players[enemy].deck)
    a = _attacker(state, seat, 9)
    state, _ = apply_action(state, catalog(), Attack(seat, a.uid, phoenix.uid))
    p = state.players[enemy]
    assert p.deck.find(phoenix.uid) and len(p.deck) == deck + 1 and not p.discard.find(phoenix.uid)


def test_796_develop_costs_1_less() -> None:
    state, seat, _ = _setup([])
    place_unit(state, seat, 1, def_id="SHR-796")
    unit = place_unit(state, seat, 1)
    state.players[seat].inf = 2
    state, _ = apply_action(state, catalog(), Develop(seat, unit.uid))
    assert state.players[seat].inf == 0


def test_797_your_units_take_1_less_damage() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    place_unit(state, enemy, 3, def_id="SHR-797")
    target = place_unit(state, enemy, 1, hp=5)
    a = _attacker(state, seat, 3)
    state, _ = apply_action(state, catalog(), Attack(seat, a.uid, target.uid))
    assert _unit(state, enemy, target.uid).current_hp == 3


def test_798_attackers_of_your_units_take_1_damage() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    place_unit(state, enemy, 3, def_id="SHR-798")
    target = place_unit(state, enemy, 1, hp=5)
    a = _attacker(state, seat, 1)
    state, _ = apply_action(state, catalog(), Attack(seat, a.uid, target.uid))
    assert _unit(state, seat, a.uid).current_hp == 8


def test_799_pay_3_for_tier_3_or_free_with_3_wind_and_3_lightning() -> None:
    state, seat, uids = _setup(["SHR-799"])
    state.players[seat].inf = 3
    state = _play(state, seat, uids[0], 0)
    p = state.players[seat]
    assert p.tiers[3].cards() and p.inf == 0
    state, seat, uids = _setup(["SHR-799"])
    with pytest.raises(IllegalAction):
        _play(state, seat, uids[0], 0)  # can't pay
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S008"] * 3 + ["MAG-S005"] * 3)
    state = _play(state, seat, uids[0], 0)
    assert state.players[seat].tiers[3].cards() and state.players[seat].inf == 0


def test_801_taunt_for_attacks_and_effects() -> None:
    state, seat, uids = _setup(["SHR-805"])
    enemy = (seat + 1) % 2
    wall = place_unit(state, enemy, 1, def_id="SHR-801", hp=5)
    wall.taunt = True
    other = place_unit(state, enemy, 1, hp=5)
    a = _attacker(state, seat, 1)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Attack(seat, a.uid, other.uid))
    assert exc.value.key == "error.must_target_taunt"
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))  # 805: 2 damage to any unit
    assert other.uid not in state.pending.prompt.options and wall.uid in state.pending.prompt.options


def test_801_taunt_set_when_played() -> None:
    state, seat, uids = _setup(["SHR-801"], mana=1)
    state = _play(state, seat, uids[0], 1)
    unit = state.players[seat].tiers[1].cards()[0]
    assert unit.taunt and unit.current_hp == 2


def test_802_hp_per_element_seen_twice() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002", "MAG-S006", "MAG-S007", "SHR-802"])
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S003"] * 2)
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    assert _play(state, seat, uids[4]).players[seat].tiers[1].cards()[0].current_hp == 2 + 4


def test_803_cleave_hits_all_enemies_on_the_tier_and_freezes() -> None:
    state, seat, _ = _setup([])
    enemy = (seat + 1) % 2
    lev = place_unit(state, seat, 1, def_id="SHR-803", hp=7)
    lev.fixed_attack = 2
    a, b, c = place_unit(state, enemy, 1, hp=5), place_unit(state, enemy, 1, hp=5), place_unit(state, enemy, 2, hp=5)
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S006"] * 4)
    state, _ = apply_action(state, catalog(), Attack(seat, lev.uid, a.uid))
    for u in (a, b):
        assert _unit(state, enemy, u.uid).current_hp == 3 and _unit(state, enemy, u.uid).status["freeze"] == 1
    assert _unit(state, enemy, c.uid).current_hp == 5


def test_804_later_influence_cards_give_1_more() -> None:
    state, seat, uids = _setup(["MAG-S001", "SHR-804", "MAG-S002", "SHR-713"])
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    assert state.players[seat].inf == 1 + 0 + 2 + 3


def test_805_vp_and_damage() -> None:
    state, seat, uids = _setup(["SHR-805"])
    target = place_unit(state, (seat + 1) % 2, 1, hp=3)
    state = _play(state, seat, uids[0], target.uid)
    assert state.players[seat].vp == 2 and _unit(state, (seat + 1) % 2, target.uid).current_hp == 1


def test_806_prepare_when_developed() -> None:
    state, seat, _ = _setup([])
    gale = place_unit(state, seat, 1, def_id="SHR-806")
    state.players[seat].inf = 3
    state.players[seat].resource = 0
    state, _ = apply_action(state, catalog(), Develop(seat, gale.uid))
    assert state.players[seat].resource == 1


def test_807_damage_per_fire_and_heal_per_two_wind() -> None:
    state, seat, uids = _setup(["SHR-807"])
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S001", "MAG-S008", "MAG-S008", "MAG-S008"])
    enemy = place_unit(state, (seat + 1) % 2, 1, hp=9)
    ally = place_unit(state, seat, 1, hp=1)
    # 2 fire (S001 + 807 itself) -> 2 hits; 4 wind (3 + 807) -> 2 heals
    state = _play(state, seat, uids[0], enemy.uid, enemy.uid, ally.uid, ally.uid)
    assert _unit(state, (seat + 1) % 2, enemy.uid).current_hp == 7 and _unit(state, seat, ally.uid).current_hp == 3


def test_808_more_inf_after_removing_a_card() -> None:
    state, seat, uids = _setup(["SHR-808"])
    assert _play(state, seat, uids[0]).players[seat].inf == 3
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S001"])
    state.players[seat].inf = 1
    state, _ = apply_action(state, catalog(), RemoveCard(seat, state.players[seat].discard.cards[0].uid))
    assert _play(state, seat, uids[0]).players[seat].inf == 4


def test_809_freezes_what_it_attacks() -> None:
    state, seat, _ = _setup([])
    biter = place_unit(state, seat, 1, def_id="SHR-809", hp=4)
    biter.fixed_attack = 1
    target = place_unit(state, (seat + 1) % 2, 1, hp=5)
    state, _ = apply_action(state, catalog(), Attack(seat, biter.uid, target.uid))
    assert _unit(state, (seat + 1) % 2, target.uid).status["freeze"] == 1


def test_810_others_lose_2_vp_not_below_0() -> None:
    state, seat, uids = _setup(["SHR-810"], players=3)
    others = [p.seat for p in state.players if p.seat != seat]
    state.players[others[0]].vp, state.players[others[1]].vp = 5, 1
    state = _play(state, seat, uids[0])
    assert (state.players[others[0]].vp, state.players[others[1]].vp) == (3, 0)


def test_811_choose_inf_or_vp() -> None:
    state, seat, uids = _setup(["SHR-811"])
    assert _play(state, seat, uids[0], 0).players[seat].inf == 3
    assert _play(state, seat, uids[0], 1).players[seat].vp == 1
