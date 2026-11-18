"""Shared market cards 731-760."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Attack, Develop, EndTurn, IllegalAction, PlayCard, Respond, apply_action
from engine.state import GameState
from engine.view import build_view
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
    return next(u for _, u in state.units_of(seat) if u.uid == uid)


def test_all_30_load() -> None:
    numbers = {c.number for c in catalog().shared_cards()}
    assert set(range(731, 761)) <= numbers


def test_731_discard_from_hand_at_eot_for_vp_even_below_two() -> None:
    state, seat, uids = _setup(["SHR-731", "MAG-S001"])
    state.players[seat].hand.cards = state.players[seat].hand.cards[:2]
    state, events = apply_action(state, catalog(), EndTurn(seat, (uids[0],)))
    p = state.players[seat]
    assert p.vp == 1 and any(e.key == "log.hand_eot_discard" for e in events)
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), EndTurn(state.current, ("nope",)))


def test_731_plays_for_5_inf() -> None:
    state, seat, uids = _setup(["SHR-731"])
    assert _play(state, seat, uids[0]).players[seat].inf == 5


def test_732_invoke_minus_one_and_draw_after_two_lightning() -> None:
    state, seat, uids = _setup(["MAG-S005", "MAG-S005", "SHR-732"], mana=3)
    for uid in uids[:2]:
        state = _play(state, seat, uid)
    hand = len(state.players[seat].hand)
    state = _play(state, seat, uids[2], 3)
    assert state.players[seat].inf == 2 + 2 and len(state.players[seat].hand) == hand  # -1 played, +1 drawn


def test_733_inf_and_prepare() -> None:
    state, seat, uids = _setup(["SHR-733"])
    state = _play(state, seat, uids[0])
    assert (state.players[seat].inf, state.players[seat].resource) == (3, 1)


def test_734_discards_a_shared_market_card() -> None:
    state, seat, uids = _setup(["SHR-734"])
    target = state.shared_market.row.slots[2]
    state = _play(state, seat, uids[0], target.uid)
    m = state.shared_market
    assert m.removed.find(target.uid) and m.row.slots[2] is not None and m.row.slots[2].uid != target.uid


def test_735_heal_all_and_shield_one() -> None:
    state, seat, uids = _setup(["SHR-735"])
    a, b = place_unit(state, seat, 1, hp=1), place_unit(state, seat, 2, hp=1)
    state = _play(state, seat, uids[0], b.uid)
    assert (_unit(state, seat, a.uid).current_hp, _unit(state, seat, b.uid).current_hp) == (2, 2)
    assert _unit(state, seat, b.uid).status["shield"] == 1


def test_736_disrupts_influence_from_each_other_player() -> None:
    state, seat, uids = _setup(["SHR-736"], players=3)
    others = [p.seat for p in state.players if p.seat != seat]
    for o in others:
        set_hand(state, o, ["MAG-S001", "MAG-S009", "MAG-S002"])
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    prompt = state.pending.prompt
    assert all(o["type"] == "influence" for o in prompt.options) and not prompt.cancellable
    for o in others:
        state, _ = apply_action(state, catalog(), Respond(seat, state.pending.prompt.options[0]["uid"]))
    assert state.pending is None
    assert all(len(state.players[o].hand) == 2 and len(state.players[o].discard) == 1 for o in others)
    assert state.undo_stack == []  # looked at hidden hands


def test_737_refresh_private_market_up_to_3_free() -> None:
    state, seat, uids = _setup(["SHR-737"])
    state = _play(state, seat, uids[0], 2)
    p = state.players[seat]
    assert p.inf == 3 and len(p.private_market.removed) == 2


def test_738_freeze_any_unit() -> None:
    state, seat, uids = _setup(["SHR-738"])
    enemy = place_unit(state, (seat + 1) % 2, 1)
    state = _play(state, seat, uids[0], enemy.uid)
    assert _unit(state, (seat + 1) % 2, enemy.uid).status["freeze"] == 1


def test_739_draw_invoke_max_2() -> None:
    state, seat, uids = _setup(["SHR-739"], mana=4)
    hand = len(state.players[seat].hand)
    state = _play(state, seat, uids[0], 4)
    assert len(state.players[seat].hand) == hand - 1 + 2 and state.players[seat].resource == 0


def test_740_bonus_with_4_other_wind_in_discard() -> None:
    state, seat, uids = _setup(["SHR-740"])
    assert _play(state, seat, uids[0]).players[seat].inf == 1
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S008"] * 4)
    assert _play(state, seat, uids[0]).players[seat].inf == 3


def test_741_play_influence_from_discard_or_gain_2() -> None:
    state, seat, uids = _setup(["SHR-741"])
    old = make_cards(state, seat, ["SHR-733"])[0]
    state.players[seat].discard.cards = [old]
    played = _play(state, seat, uids[0], 0, old.uid)
    assert played.players[seat].inf == 3 and played.players[seat].resource == 1
    assert _play(state, seat, uids[0], 1).players[seat].inf == 2


def test_742_optional_stun_all_and_refresh_every_market() -> None:
    hand = ["MAG-S005", "MAG-S005", "SHR-736", "SHR-736", "SHR-742"]
    state, seat, uids = _setup(hand)
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S001"] * 2)
    mine = place_unit(state, seat, 1)
    for o in (p.seat for p in state.players if p.seat != seat):
        set_hand(state, o, ["MAG-S009"])  # no influence to disrupt: 736 has no prompt
    for uid in uids[:4]:
        state = _play(state, seat, uid)
    removed_before = len(state.shared_market.removed)
    state = _play(state, seat, uids[4], 0, 0)
    assert _unit(state, seat, mine.uid).status["stun"] == 1
    assert state.players[seat].inf == 2 + 2 + 3 + 1
    assert len(state.shared_market.removed) == removed_before + 1
    assert all(len(p.private_market.removed) == 1 for p in state.players)


def test_743_develop_twice_for_free() -> None:
    state, seat, uids = _setup(["SHR-743"])
    unit = place_unit(state, seat, 1)
    state = _play(state, seat, uids[0], unit.uid, unit.uid)
    assert state.players[seat].tiers[3].find(unit.uid) and state.players[seat].inf == 0


def test_744_one_unit_of_each_opponent_on_tiers_1_3() -> None:
    state, seat, uids = _setup(["SHR-744"], mana=1, players=3)
    targets = []
    for o in (p.seat for p in state.players if p.seat != seat):
        targets.append((o, place_unit(state, o, 1, hp=5)))
        place_unit(state, o, 4, hp=5)  # out of reach (tier 4)
    state = _play(state, seat, uids[0], 1, targets[0][1].uid, targets[1][1].uid)  # 1+1(class)+1 = 3
    assert all(_unit(state, o, u.uid).current_hp == 2 for o, u in targets)


def test_745_prepare_and_scout_3_discard_any() -> None:
    state, seat, uids = _setup(["SHR-745"])
    state.players[seat].deck.cards = make_cards(state, seat, ["MAG-S001", "MAG-S002", "MAG-S003", "MAG-S004"])
    top = [c.uid for c in state.players[seat].deck]
    state = _play(state, seat, uids[0], [top[1]])
    p = state.players[seat]
    assert p.resource == 1 and [c.uid for c in p.deck] == [top[0], top[2], top[3]]


def test_746_swap_own_units_and_heal() -> None:
    state, seat, uids = _setup(["SHR-746"])
    low, high = place_unit(state, seat, 1, hp=1), place_unit(state, seat, 3, hp=1)
    state = _play(state, seat, uids[0], [low.uid, high.uid])
    assert state.players[seat].tiers[3].find(low.uid) and state.players[seat].tiers[1].find(high.uid)
    assert _unit(state, seat, low.uid).current_hp == 2


def test_746_with_shadow_also_swaps_enemies_and_damages_them() -> None:
    state, seat, uids = _setup(["SHR-736", "SHR-736", "SHR-746"])
    enemy = (seat + 1) % 2
    set_hand(state, enemy, ["MAG-S009"])
    a, b = place_unit(state, seat, 1), place_unit(state, seat, 2)
    x, y = place_unit(state, enemy, 1, hp=3), place_unit(state, enemy, 2, hp=3)
    for uid in uids[:2]:
        state = _play(state, seat, uid)
    state = _play(state, seat, uids[2], [a.uid, b.uid], [x.uid, y.uid])
    assert state.players[enemy].tiers[2].find(x.uid) and _unit(state, enemy, x.uid).current_hp == 2


def test_747_shield_plus_2_hp_after_3_water() -> None:
    state, seat, uids = _setup(["MAG-S006", "MAG-S007", "MAG-S010", "SHR-747"])
    unit = place_unit(state, seat, 1, hp=1)
    for uid in uids[:2]:
        state = _play(state, seat, uid)
    state = _play(state, seat, uids[2])  # 010 (water/shadow), no mana -> invoke 1 automatically, no VP
    state = _play(state, seat, uids[3], unit.uid)
    u = _unit(state, seat, unit.uid)
    assert u.status["shield"] == 1 and u.current_hp == 3


def test_748_reveal_two_wind_to_prepare_again_and_lock_them() -> None:
    state, seat, uids = _setup(["SHR-748", "MAG-S008", "SHR-740", "MAG-S001"])
    state = _play(state, seat, uids[0], [uids[1], uids[2]])
    p = state.players[seat]
    assert p.resource == 3 and set(p.locked_cards) == {uids[1], uids[2]}
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, uids[1]))
    assert exc.value.key == "error.card_locked"
    assert uids[1] not in build_view(state, catalog(), seat)["legal"]["playable"]


def test_749_scout_5_draw_1_then_reorder_or_discard() -> None:
    state, seat, uids = _setup(["SHR-749"])
    state.players[seat].deck.cards = make_cards(state, seat, ["MAG-S001", "MAG-S002", "MAG-S003", "MAG-S004", "MAG-S005", "MAG-S006"])
    top = [c.uid for c in state.players[seat].deck]
    reordered = _play(state, seat, uids[0], top[0], 1, [top[4], top[1], top[3], top[2]])
    assert [c.uid for c in reordered.players[seat].deck] == [top[4], top[1], top[3], top[2], top[5]]
    discarded = _play(state, seat, uids[0], top[0], 0)
    assert [c.uid for c in discarded.players[seat].deck] == [top[5]] and len(discarded.players[seat].discard) == 4


def test_750_prepare_x2_and_2_damage() -> None:
    state, seat, uids = _setup(["SHR-750"])
    enemy = place_unit(state, (seat + 1) % 2, 1, hp=3)
    state = _play(state, seat, uids[0], enemy.uid)
    assert state.players[seat].resource == 2 and _unit(state, (seat + 1) % 2, enemy.uid).current_hp == 1


def test_751_plus_2_attack_and_two_attacks() -> None:
    state, seat, uids = _setup(["SHR-751"])
    mine = place_unit(state, seat, 1)
    mine.fixed_attack = 1
    e1, e2 = place_unit(state, (seat + 1) % 2, 1, hp=9), place_unit(state, (seat + 1) % 2, 1, hp=9)
    state = _play(state, seat, uids[0], mine.uid)
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, e1.uid))
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, e2.uid))
    assert _unit(state, (seat + 1) % 2, e1.uid).current_hp == 6 and _unit(state, (seat + 1) % 2, e2.uid).current_hp == 6
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Attack(seat, mine.uid, e1.uid))


def test_752_stun_and_1_damage_to_a_tier() -> None:
    state, seat, uids = _setup(["SHR-752"])
    a = place_unit(state, (seat + 1) % 2, 2, hp=3)
    b = place_unit(state, seat, 2, hp=3)
    state = _play(state, seat, uids[0], 2)
    for s_, u in (((seat + 1) % 2, a), (seat, b)):
        assert _unit(state, s_, u.uid).status["stun"] == 1 and _unit(state, s_, u.uid).current_hp == 2


def test_753_shuffle_up_to_invoke_cards_into_deck() -> None:
    state, seat, uids = _setup(["SHR-753"], mana=2)
    old = make_cards(state, seat, ["MAG-S001", "MAG-S002", "MAG-S003"])
    state.players[seat].discard.cards = list(old)
    deck = len(state.players[seat].deck)
    state = _play(state, seat, uids[0], 2, [old[0].uid, old[1].uid, old[2].uid])  # 2+1 = 3
    p = state.players[seat]
    assert len(p.deck) == deck + 3 and p.discard.is_empty()


def test_754_all_units_extra_attack() -> None:
    state, seat, uids = _setup(["SHR-754"])
    mine = place_unit(state, seat, 1)
    mine.fixed_attack = 1
    enemy = place_unit(state, (seat + 1) % 2, 1, hp=9)
    state = _play(state, seat, uids[0])
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, enemy.uid))
    state, _ = apply_action(state, catalog(), Attack(seat, mine.uid, enemy.uid))
    assert _unit(state, (seat + 1) % 2, enemy.uid).current_hp == 7


def test_755_two_different_units_one_invoke() -> None:
    state, seat, uids = _setup(["SHR-755"], mana=1)
    place_unit(state, seat, 1)
    a, b = place_unit(state, (seat + 1) % 2, 1, hp=9), place_unit(state, (seat + 1) % 2, 1, hp=9)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    state, _ = apply_action(state, catalog(), Respond(seat, 2))  # prepare 1 -> 2 mana; value 2+1 = 3
    state, _ = apply_action(state, catalog(), Respond(seat, a.uid))  # 4 damage
    assert a.uid not in state.pending.prompt.options
    state, _ = apply_action(state, catalog(), Respond(seat, b.uid))  # 2 damage
    assert (_unit(state, (seat + 1) % 2, a.uid).current_hp, _unit(state, (seat + 1) % 2, b.uid).current_hp) == (5, 7)


def test_756_vp_and_stun_invoke_enemy_units() -> None:
    state, seat, uids = _setup(["SHR-756"], mana=1)
    e = [place_unit(state, (seat + 1) % 2, 1) for _ in range(2)] + [place_unit(state, (seat + 1) % 2, 2)]
    place_unit(state, seat, 1)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    state, _ = apply_action(state, catalog(), Respond(seat, 1))  # value 2
    assert state.pending.prompt.max == 2 and len(state.pending.prompt.options) == 3  # enemies only
    state, _ = apply_action(state, catalog(), Respond(seat, [e[0].uid, e[2].uid]))
    assert state.players[seat].vp == 1
    assert [_unit(state, (seat + 1) % 2, u.uid).status["stun"] for u in e] == [1, 0, 1]


def test_757_next_develop_cheaper_per_prepare() -> None:
    state, seat, uids = _setup(["SHR-757"])
    unit = place_unit(state, seat, 1)
    state = _play(state, seat, uids[0])
    state.players[seat].inf = 1
    assert build_view(state, catalog(), seat)["legal"]["develop"][unit.uid]["cost"] == 1  # 3 - 2 prepares
    state, _ = apply_action(state, catalog(), Develop(seat, unit.uid))
    assert state.players[seat].inf == 0 and state.players[seat].turn_modifiers == []


def test_758_vp_per_kill_while_in_discard() -> None:
    state, seat, uids = _setup(["SHR-758", "SHR-725"])
    weak = place_unit(state, (seat + 1) % 2, 1, hp=2)
    state = _play(state, seat, uids[0])  # in "played this turn" = in the discard pile for this rule
    state = _play(state, seat, uids[1], weak.uid)
    assert state.players[seat].vp == 1


def test_759_spares_your_units_after_2_wind() -> None:
    state, seat, uids = _setup(["MAG-S008", "MAG-S008", "SHR-759"], mana=1)
    mine, theirs = place_unit(state, seat, 1, hp=5), place_unit(state, (seat + 1) % 2, 1, hp=5)
    state = _play(state, seat, uids[0], 0)  # wind scout spells: spend 0 mana
    state = _play(state, seat, uids[1], 0)
    state = _play(state, seat, uids[2], 1, 1)
    assert _unit(state, seat, mine.uid).current_hp == 5 and _unit(state, (seat + 1) % 2, theirs.uid).current_hp == 3


def test_760_degrades_players_minus_one_times() -> None:
    state, seat, uids = _setup(["SHR-760"], players=4)
    enemy = (seat + 1) % 4
    unit = place_unit(state, enemy, 3)
    other = place_unit(state, (seat + 2) % 4, 2)
    hand = len(state.players[seat].hand)
    state = _play(state, seat, uids[0], unit.uid, unit.uid, other.uid)  # 3 degrades: same unit twice is fine
    assert state.players[enemy].tiers[1].find(unit.uid)
    assert state.players[(seat + 2) % 4].tiers[1].find(other.uid)
    assert len(state.players[seat].hand) == hand - 1 + 1


def test_760_two_players_degrade_once() -> None:
    state, seat, uids = _setup(["SHR-760"], players=2)
    unit = place_unit(state, (seat + 1) % 2, 3)
    state = _play(state, seat, uids[0], unit.uid)
    assert state.players[(seat + 1) % 2].tiers[2].find(unit.uid)
