"""Basic supply (701-712) and shared market cards (713+), added in batches."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import Buy, IllegalAction, PlayCard, Refresh, Respond, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_cards, make_game, place_unit, set_hand


def _setup(hand: list[str], mana: int = 0) -> tuple[GameState, int, list[str]]:
    state = make_game()
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


# ---- basic supply -----------------------------------------------------------------------------


def test_basic_supply_is_701_to_712_and_not_in_the_market() -> None:
    assert [c.number for c in catalog().basic_cards()] == list(range(701, 713))
    state = make_game()
    assert len(state.basic_supply) == 12
    market_ids = {c.def_id for c in [*state.shared_market.row.cards(), *state.shared_market.deck]}
    assert not any(cid in market_ids for cid in (f"SHR-{n}" for n in range(701, 713)))


def test_basic_cards_gain_2_inf() -> None:
    for number in range(701, 713):
        state, seat, uids = _setup([f"SHR-{number}"])
        assert _play(state, seat, uids[0]).players[seat].inf == 2, number


def test_buy_from_basic_supply_any_time_at_printed_price() -> None:
    state = make_game()
    seat = state.current
    state.players[seat].inf = 3
    assert build_view(state, catalog(), seat)["legal"]["market"]["basic_buy"] is True
    state, events = apply_action(state, catalog(), Buy(seat, "basic", 0))
    p = state.players[seat]
    assert p.inf == 0 and len(state.basic_supply) == 11 and p.discard.cards[-1].def_id.startswith("SHR-7")
    assert state.undo_stack, "nothing hidden was revealed, so the buy is undoable"
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Refresh(seat, "basic"))


def test_empty_basic_supply_cannot_be_bought() -> None:
    state = make_game()
    seat = state.current
    state.basic_supply.cards = []
    state.players[seat].inf = 5
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Buy(seat, "basic", 0))
    assert exc.value.key == "error.empty_slot"


def test_shared_market_deals_6_from_713_and_up() -> None:
    state = make_game()
    numbers = [catalog().card(c.def_id).number for c in state.shared_market.row.cards()]
    assert len(numbers) == 6 and all(n >= 713 for n in numbers)


# ---- 713-720 ----------------------------------------------------------------------------------


def test_713_three_inf_after_4_primary_cards() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002", "MAG-S006", "MAG-S005", "SHR-713", "MAG-S007"])
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S003"] * 2)  # room to keep playing
    for uid in uids[:4]:  # fire, fire, water, lightning -> 3 primary
        state = _play(state, seat, uid)
    assert _play(state, seat, uids[4]).players[seat].inf == 4 + 2
    state = _play(state, seat, uids[5])  # 4th primary card
    assert _play(state, seat, uids[4]).players[seat].inf == 5 + 3


def test_714_inf_and_one_hp_to_any_unit() -> None:
    state, seat, uids = _setup(["SHR-714"])
    enemy = place_unit(state, (seat + 1) % 2, 1, hp=1)
    state = _play(state, seat, uids[0], enemy.uid)
    assert state.players[seat].inf == 2
    assert next(u for _, u in state.units_of((seat + 1) % 2)).current_hp == 2


def test_715_puts_another_lightning_card_on_bottom_of_deck() -> None:
    state, seat, uids = _setup(["MAG-S005", "MAG-S005", "SHR-715"])
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])
    state = _play(state, seat, uids[2], uids[0])
    p = state.players[seat]
    assert p.deck.cards[-1].uid == uids[0] and p.in_play.find(uids[0]) is None
    assert p.inf == 4  # its +1 inf stays


def test_715_needs_two_other_lightning_cards() -> None:
    state, seat, uids = _setup(["MAG-S005", "SHR-715"])
    state = _play(state, seat, uids[0])
    state = _play(state, seat, uids[1])  # no prompt
    assert state.players[seat].inf == 3


def test_716_needs_your_unit_to_damage() -> None:
    state, seat, uids = _setup(["SHR-716"])
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert exc.value.key == "error.requirement_not_met"
    assert uids[0] not in build_view(state, catalog(), seat)["legal"]["playable"]
    mine = place_unit(state, seat, 1, hp=3)
    place_unit(state, (seat + 1) % 2, 1, hp=3)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    prompt = state.pending.prompt
    assert prompt.options == (mine.uid,) and not prompt.allow_skip  # own units only, can't skip
    state, _ = apply_action(state, catalog(), Respond(seat, mine.uid))
    assert state.players[seat].inf == 3
    assert next(u for _, u in state.units_of(seat)).current_hp == 2


def test_717_prepare_then_invoke_inf_max_4() -> None:
    state, seat, uids = _setup(["SHR-717"], mana=4)
    state = _play(state, seat, uids[0], 4)  # prepare: 4 (limit) -> invoke 4 -> 4 inf
    assert (state.players[seat].inf, state.players[seat].resource) == (4, 0)
    state, seat, uids = _setup(["SHR-717"], mana=2)
    state = _play(state, seat, uids[0], 3)  # prepare 2 -> 3, spend 3
    assert state.players[seat].inf == 3


def test_718_counts_units_on_tier_2_plus_max_4() -> None:
    state, seat, uids = _setup(["SHR-718"])
    place_unit(state, seat, 1)
    place_unit(state, seat, 2)
    place_unit(state, seat, 3)
    assert _play(state, seat, uids[0]).players[seat].inf == 3
    place_unit(state, seat, 4)  # 2 players: one shared spot
    place_unit(state, seat, 2)
    assert _play(state, seat, uids[0]).players[seat].inf == 4  # 1 + 4 units, capped at 4


def test_719_counts_prepares_this_turn_max_5() -> None:
    state, seat, uids = _setup(["MAG-P034", "SHR-719"])
    state = _play(state, seat, uids[0])  # prepare x2
    state = _play(state, seat, uids[1])  # prepare (3rd) -> 3 inf
    assert state.players[seat].inf == 2 + 3


def test_720_invoke_inf_and_optional_discard_for_2() -> None:
    state, seat, uids = _setup(["SHR-720"], mana=3)
    state = _play(state, seat, uids[0], 3, uids[1])  # 3 inf + discard a card for 2
    p = state.players[seat]
    assert p.inf == 5 and p.discard.find(uids[1]) is not None and len(p.hand) == 5
    state, seat, uids = _setup(["SHR-720"], mana=3)
    assert _play(state, seat, uids[0], 3, None).players[seat].inf == 3


# ---- 721-730 ----------------------------------------------------------------------------------


def test_721_inf_and_shield_own_unit() -> None:
    state, seat, uids = _setup(["SHR-721"])
    mine = place_unit(state, seat, 1)
    place_unit(state, (seat + 1) % 2, 1)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert state.pending.prompt.options == (mine.uid,)
    state, _ = apply_action(state, catalog(), Respond(seat, mine.uid))
    assert next(u for _, u in state.units_of(seat)).status["shield"] == 1 and state.players[seat].inf == 2


def test_722_prepare_per_occupied_tier_max_3() -> None:
    state, seat, uids = _setup(["SHR-722"])
    for tier in (1, 2, 3, 4):
        place_unit(state, seat, tier)
    state = _play(state, seat, uids[0])
    assert (state.players[seat].inf, state.players[seat].resource) == (1, 3)  # 3 prepares from 0 (limit 4)


def test_723_damage_is_mandatory_unless_4_lightning_in_discard() -> None:
    state, seat, uids = _setup(["SHR-723"])
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, uids[0]))  # no unit to damage
    assert exc.value.key == "error.requirement_not_met"
    state.players[seat].discard.cards = make_cards(state, seat, ["MAG-S005"] * 3)  # + this card = 4
    state = _play(state, seat, uids[0])
    assert state.players[seat].inf == 5


def test_723_deals_3_to_your_unit() -> None:
    state, seat, uids = _setup(["SHR-723"])
    mine = place_unit(state, seat, 1, hp=4)
    state = _play(state, seat, uids[0], mine.uid)
    assert state.players[seat].inf == 5 and next(u for _, u in state.units_of(seat)).current_hp == 1


def test_724_degrade_own_unit_for_its_develop_cost() -> None:
    state, seat, uids = _setup(["SHR-724"])
    high = place_unit(state, seat, 3)
    state = _play(state, seat, uids[0], high.uid)
    assert state.players[seat].inf == 2 + 4
    assert next(t for t, u in state.units_of(seat) if u.uid == high.uid) == 2


def test_724_from_tier4_goes_to_owner_tier3_and_needs_free_spot() -> None:
    state, seat, uids = _setup(["SHR-724"])
    top = place_unit(state, seat, 4)
    place_unit(state, seat, 3)  # tier 3 full (1 spot): the tier-4 unit can't degrade
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    assert top.uid not in state.pending.prompt.options
    state, seat, uids = _setup(["SHR-724"])
    top = place_unit(state, seat, 4)
    state = _play(state, seat, uids[0], top.uid)
    assert state.players[seat].tiers[3].find(top.uid) and state.players[seat].inf == 2 + 5


def test_725_extra_inf_when_it_kills() -> None:
    state, seat, uids = _setup(["SHR-725"])
    weak = place_unit(state, (seat + 1) % 2, 1, hp=2)
    assert _play(state, seat, uids[0], weak.uid).players[seat].inf == 4
    state, seat, uids = _setup(["SHR-725"])
    tough = place_unit(state, (seat + 1) % 2, 1, hp=5)
    assert _play(state, seat, uids[0], tough.uid).players[seat].inf == 2


def test_726_can_be_bought_with_3_vp() -> None:
    state = make_game()
    seat = state.current
    card = make_cards(state, -1, ["SHR-726"])[0]
    state.shared_market.row.slots[2] = card
    state.players[seat].vp = 2
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Buy(seat, "shared", 2, "vp"))
    assert exc.value.key == "error.not_enough_vp"
    state.players[seat].vp = 5
    assert {"market": "shared", "slot": 2, "vp": 3} in build_view(state, catalog(), seat)["legal"]["market"]["alt_buy"]
    state, _ = apply_action(state, catalog(), Buy(seat, "shared", 2, "vp"))
    p = state.players[seat]
    assert p.vp == 2 and p.inf == 0 and p.discard.find(card.uid)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), Buy(seat, "shared", 2, "vp"))  # the new card has no VP cost
    assert exc.value.key in ("error.no_alt_cost", "error.empty_slot")


def test_727_counts_enemy_kills_this_turn_max_5() -> None:
    state, seat, uids = _setup(["SHR-725", "SHR-727"])
    weak = place_unit(state, (seat + 1) % 2, 1, hp=1)
    state = _play(state, seat, uids[0], weak.uid)  # kill: +4 inf
    state = _play(state, seat, uids[1])
    assert state.players[seat].inf == 4 + 4
    state, seat, uids = _setup(["SHR-727"])
    state.players[seat].enemy_kills_this_turn = 4
    assert _play(state, seat, uids[0]).players[seat].inf == 5


def test_728_scout_4_and_discard_any() -> None:
    state, seat, uids = _setup(["SHR-728"])
    p = state.players[seat]
    p.deck.cards = make_cards(state, seat, ["MAG-S001", "MAG-S005", "MAG-S006", "MAG-S007", "MAG-S008"])
    top = [c.uid for c in p.deck]
    state, _ = apply_action(state, catalog(), PlayCard(seat, uids[0]))
    prompt = state.pending.prompt
    assert prompt.kind == "choose_cards" and (prompt.min, prompt.max) == (0, 4) and not prompt.cancellable
    state, _ = apply_action(state, catalog(), Respond(seat, [top[0], top[2]]))
    p = state.players[seat]
    assert [c.uid for c in p.deck] == [top[1], top[3], top[4]]
    assert p.discard.find(top[0]) and p.discard.find(top[2]) and p.inf == 3


def test_729_free_develop() -> None:
    state, seat, uids = _setup(["SHR-729"])
    unit = place_unit(state, seat, 1)
    state = _play(state, seat, uids[0], unit.uid)
    assert state.players[seat].inf == 1 and state.players[seat].tiers[2].find(unit.uid)


def test_730_bigger_bonus_after_4_other_fire_or_water_cards() -> None:
    state, seat, uids = _setup(["MAG-S001", "MAG-S002", "MAG-S006", "SHR-730", "MAG-S007"])
    state.players[seat].hand.cards += make_cards(state, seat, ["MAG-S003"] * 2)
    for uid in uids[:3]:
        state = _play(state, seat, uid)
    small = _play(state, seat, uids[3])
    assert (small.players[seat].inf, small.players[seat].resource) == (3 + 3, 1)
    state = _play(state, seat, uids[4])  # 4th fire/water card
    big = _play(state, seat, uids[3])
    assert (big.players[seat].inf, big.players[seat].resource) == (4 + 4, 2)
