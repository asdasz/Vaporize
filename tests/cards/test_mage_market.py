"""End-to-end behaviour of the Mage market cards (031-045)."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Attack, CancelChoice, EndTurn, IllegalAction, PlayCard, Respond, apply_action
from engine.state import GameState
from tests.helpers import catalog, make_cards, make_game, place_unit, set_hand

FILLER = ["MAG-S001"] * 6


def _setup(hand: list[str], mana: int = 0) -> tuple[GameState, int, list[str]]:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, hand + FILLER[: max(0, 7 - len(hand))])
    state.players[seat].resource = mana
    return state, seat, [c.uid for c in cards]


def _play(state: GameState, seat: int, uid: str, *answers: Any) -> GameState:
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    for answer in answers:
        assert state.pending is not None, "expected a prompt"
        state, _ = apply_action(state, catalog(), Respond(seat, answer))
    assert state.pending is None, f"unexpected prompt {state.pending.prompt.kind if state.pending else ''}"
    return state


def test_market_has_15_cards_031_to_045() -> None:
    cards = catalog().private_cards("mage")
    assert [c.number for c in cards] == list(range(31, 46))


def test_031_prepare_only_after_4_elements() -> None:
    hand = ["MAG-S001", "MAG-S005", "MAG-S006", "MAG-S008", "MAG-P031"]  # fire, lightning, water, wind
    state, seat, uids = _setup(hand, mana=0)
    state.players[seat].deck.cards = make_cards(state, seat, ["MAG-S002"] * 3)
    for uid in uids[:3]:
        state = _play(state, seat, uid)
    state = _play(state, seat, uids[3])  # wind scout spell: 0 mana -> value 1, scouts 0 cards
    state = _play(state, seat, uids[4])
    p = state.players[seat]
    assert p.inf == 3 + 2
    assert p.resource == 2  # prepare x2 (up to limit 4)


def test_031_no_prepare_with_3_elements() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S005", "MAG-S006", "MAG-P031"])
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    assert state.players[seat].resource == 0


def test_032_invoke_inf_and_next_fire_spell_bonus() -> None:
    state, seat, uids = _setup(["MAG-P032", "MAG-S010"], mana=4)
    state = _play(state, seat, uids[0], 2)  # influence: no spell bonus -> 2 inf
    assert state.players[seat].inf == 2
    # next spell (010, water/shadow): +1 -> spend 2: 2 + 1 (class) + 1 = 4 -> VP
    state = _play(state, seat, uids[1], 2)
    assert state.players[seat].vp == 1
    assert state.players[seat].turn_modifiers == []


def test_032_fire_spell_gets_plus_two() -> None:
    state, seat, uids = _setup(["MAG-P032", "MAG-S009"], mana=1)
    enemy = place_unit(state, (seat + 1) % 2, 1, hp=9)
    state = _play(state, seat, uids[0], 0)
    state = _play(state, seat, uids[1], 1, enemy.uid)  # 1 + 1 (class) + 2 = 4 damage
    assert next(u for _, u in state.units_of((seat + 1) % 2)).current_hp == 5


def test_033_choose_one_prepare_x4_exceeds_limit() -> None:
    state, seat, uids = _setup(["MAG-P033"], mana=3)
    state = _play(state, seat, uids[0], 2)
    assert state.players[seat].resource == 7


def test_033_choose_inf_or_draw() -> None:
    state, seat, uids = _setup(["MAG-P033"])
    assert _play(state, seat, uids[0], 0).players[seat].inf == 4
    hand = len(state.players[seat].hand)
    assert len(_play(state, seat, uids[0], 1).players[seat].hand) == hand - 1 + 2


def test_034_inf_and_prepare_x2_past_limit() -> None:
    state, seat, uids = _setup(["MAG-P034"], mana=4)
    state = _play(state, seat, uids[0])
    assert (state.players[seat].inf, state.players[seat].resource) == (2, 6)


def test_035_counts_unique_elements_on_other_cards() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002", "MAG-S006", "MAG-P035"])
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    assert state.players[seat].inf == 3 + (1 + 2)  # fire + water


def test_036_single_target_or_split_on_ally_tiers() -> None:
    state, seat, uids = _setup(["MAG-P036"], mana=1)
    enemy = (seat + 1) % 2
    place_unit(state, seat, 2)
    a = place_unit(state, enemy, 2, hp=5)
    far = place_unit(state, enemy, 3, hp=5)
    single = _play(state, seat, uids[0], 0, 1, far.uid)  # 1 + 1 + 1 = 3 to any unit
    assert next(u for _, u in single.units_of(enemy) if u.uid == far.uid).current_hp == 2
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    state, _ = apply_action(state, catalog(), Respond(seat, 1))
    state, _ = apply_action(state, catalog(), Respond(seat, 1))  # value 1 + 1 + 2 = 4, split
    prompt = state.pending.prompt
    assert prompt.kind == "split_damage" and far.uid not in prompt.options and a.uid in prompt.options
    state, _ = apply_action(state, catalog(), Respond(seat, {a.uid: 4}))
    assert next(u for _, u in state.units_of(enemy) if u.uid == a.uid).current_hp == 1


def test_037_extra_vp_with_units_on_two_tiers() -> None:
    state, seat, uids = _setup(["MAG-P037"])
    assert _play(state, seat, uids[0]).players[seat].vp == 1
    place_unit(state, seat, 1)
    place_unit(state, seat, 2)
    assert _play(state, seat, uids[0]).players[seat].vp == 2


def test_038_plays_a_spell_from_discard() -> None:
    state, seat, uids = _setup(["MAG-P038"], mana=3)
    spell, influence = make_cards(state, seat, ["MAG-S010", "MAG-S002"])
    state.players[seat].discard.cards = [spell, influence]
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert [o["uid"] for o in state.pending.prompt.options] == [spell.uid]  # spells only
    state, _ = apply_action(state, catalog(), Respond(seat, spell.uid))
    state, _ = apply_action(state, catalog(), Respond(seat, 3))  # 010: 3 + 1 = 4 -> 1 VP
    p = state.players[seat]
    assert p.vp == 1 and p.in_play.find(spell.uid) is not None
    assert [x.def_id for x in p.played_this_turn] == ["MAG-P038", "MAG-S010"]


def test_039_everything_and_no_cancel_after_draw() -> None:
    state, seat, uids = _setup(["MAG-P039"])
    place_unit(state, (seat + 1) % 2, 1)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert state.pending.prompt.kind == "choose_unit" and not state.pending.prompt.cancellable
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), CancelChoice(seat))
    state, _ = apply_action(state, catalog(), Respond(seat, None))
    p = state.players[seat]
    assert (p.vp, p.inf, len(p.hand)) == (1, 1, 7)


def test_040_damages_all_units_on_chosen_tier() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-P040"], mana=1)
    enemy = (seat + 1) % 2
    a = place_unit(state, enemy, 2, hp=5)
    b = place_unit(state, seat, 2, hp=5)
    c = place_unit(state, enemy, 1, hp=5)
    state = _play(state, seat, uids[0])  # one other fire card
    state = _play(state, seat, uids[1], 1, 2)  # 1 + 1 (class) + 1 fire = 3 to tier 2
    hp = {u.uid: u.current_hp for p in (seat, enemy) for _, u in state.units_of(p)}
    assert (hp[a.uid], hp[b.uid], hp[c.uid]) == (2, 2, 5)


def test_041_next_spell_twice_same_invoke_and_vp_per_kill() -> None:
    state, seat, uids = _setup(["MAG-P041", "MAG-S009"], mana=2)
    enemy = (seat + 1) % 2
    a = place_unit(state, enemy, 1, hp=3)
    b = place_unit(state, enemy, 1, hp=3)
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1], 2, a.uid, b.uid)  # invoke once (3 dmg), two targets
    p = state.players[seat]
    assert state.units_of(enemy) == [] and p.vp == 2 and p.resource == 0


def test_042_attack_boost_and_vp_per_attack_kill() -> None:
    state, seat, uids = _setup(["MAG-P042"], mana=2)
    enemy = (seat + 1) % 2
    mine = place_unit(state, seat, 1, hp=2)
    target = place_unit(state, enemy, 1, hp=3)
    state = _play(state, seat, uids[0], 2)  # +3 attack this turn
    attacker = next(u for _, u in state.units_of(seat) if u.uid == mine.uid)
    assert attacker.attack_value == 3
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, target.uid))
    assert state.units_of(enemy) == [] and state.players[seat].vp == 1
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert next(u for _, u in state.units_of(seat)).temp_attack == 0


def test_043_health_is_invoke_plus_one_and_eot_vp() -> None:
    hand = ["MAG-P043", "MAG-S001", "MAG-S005", "MAG-S006", "MAG-S008"]
    state, seat, uids = _setup(hand, mana=2)
    state.players[seat].deck.cards = make_cards(state, seat, ["MAG-S002"] * 3)
    state = _play(state, seat, uids[0], 2)
    unit = state.players[seat].tiers[1].cards()[0]
    assert unit.current_hp == 3  # units get no spell bonus
    for uid in uids[1:4]:
        state = _play(state, seat, uid)
    shadow = make_cards(state, seat, ["MAG-S010"])[0]  # water + shadow
    state.players[seat].hand.put_bottom(shadow)
    state = _play(state, seat, uids[4])  # wind (008, no mana left -> automatic)
    state = _play(state, seat, shadow.uid)
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].vp == 1


def test_044_gains_2_inf_once_when_4_non_primary_cards_are_reached() -> None:
    state = make_game()
    seat = state.current
    lightning = ["MAG-S005"] * 6
    cards = set_hand(state, seat, ["MAG-P044", *lightning[:5], "MAG-S001"])
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S005"] * 4)  # plenty to play
    uids = [c.uid for c in state.players[seat].hand]
    state = _play(state, seat, uids[0])  # the unit
    for uid in uids[1:4]:
        state = _play(state, seat, uid)
    assert state.players[seat].inf == 3
    state = _play(state, seat, uids[4])  # 4th non-primary card
    assert state.players[seat].inf == 4 + 2
    for uid in uids[5:9]:  # 5th..8th: no more triggers this turn
        state = _play(state, seat, uid)
    assert state.players[seat].inf == 8 + 2


def test_044_fires_on_the_next_card_if_already_past_four() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, [*["MAG-S005"] * 5, "MAG-P044", "MAG-S001"])
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S001"] * 2)
    for card in cards[:5]:  # 5 lightning cards before the unit is on the board
        state = _play(state, seat, card.uid)
    state = _play(state, seat, cards[5].uid)  # unit enters: check right away -> fires
    assert state.players[seat].inf == 5 + 2
    state = _play(state, seat, cards[6].uid)
    assert state.players[seat].inf == 6 + 2


def test_044_resets_next_turn() -> None:
    state = make_game()
    seat = state.current
    unit = place_unit(state, seat, 1, def_id="MAG-P044", hp=4)
    state.players[seat].turn_flags = [f"{unit.uid}:x"]
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    assert state.players[seat].turn_flags == []


def test_045_adds_one_to_spells_invoke() -> None:
    state, seat, uids = _setup(["MAG-S010"], mana=2)
    place_unit(state, seat, 1, def_id="MAG-P045")
    state = _play(state, seat, uids[0], 2)  # 2 + 1 (class) + 1 (unit) = 4
    assert state.players[seat].vp == 1
