from __future__ import annotations

import pytest

from engine.actions import EndTurn, IllegalAction, PlayCard, apply_action, legal_plays
from tests.helpers import catalog, catalog_with, make_game, set_hand, spell_def


def test_play_influence_gains_inf_and_moves_to_in_play() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S01"] * 7)
    new, events = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    p = new.players[seat]
    assert p.inf == 1
    assert len(p.hand) == 6 and len(p.in_play) == 1
    assert [e.key for e in events][:2] == ["log.card_played", "log.gain_inf"]


def test_apply_action_does_not_mutate_input_state() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S01"] * 7)
    apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    assert len(state.players[seat].hand) == 7


def test_can_play_at_most_five_of_seven() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S01"] * 7)
    for card in cards[:5]:
        state, _ = apply_action(state, catalog(), PlayCard(seat, card.uid))
    assert legal_plays(state, catalog(), seat) == []
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, cards[5].uid))
    assert exc.value.key == "error.min_hand"


def test_cannot_play_on_other_players_turn() -> None:
    state = make_game()
    other = (state.current + 1) % 2
    card = state.players[other].hand.cards[0]
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(other, card.uid))
    assert exc.value.key == "error.not_your_turn"


def test_unit_enters_tier1_and_blocks_when_full() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S06"] * 3 + ["MAG-S01"] * 4)
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[1].uid))
    tier1 = state.players[seat].tiers[1]
    assert len(tier1.cards()) == 2
    assert tier1.cards()[0].current_hp == 2
    assert cards[2].uid not in legal_plays(state, catalog(), seat)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, cards[2].uid))
    assert exc.value.key == "error.tier_full"


def test_every_mock_card_gives_one_inf() -> None:
    state = make_game()
    seat = state.current
    for def_id in catalog().cards:
        cards = set_hand(state, seat, [def_id] + ["MAG-S01"] * 6)
        state.players[seat].inf = 0
        after, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
        assert after.players[seat].inf == 1, def_id


def test_draw_effect_lets_you_play_more_cards() -> None:
    cat = catalog_with(spell_def("TST-001", [{"do": "draw", "count": 1}]))
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["TST-001"] + ["MAG-S01"] * 6)
    state, _ = apply_action(state, cat, PlayCard(seat, cards[0].uid))
    assert len(state.players[seat].hand) == 7


def test_condition_counts_only_earlier_cards() -> None:
    cat = catalog_with(
        spell_def("TST-002", [
            {"if": {"played_this_turn": {"element": "water", "min": 2, "other": True}},
             "then": [{"do": "gain_vp", "amount": 1}]},
        ]),
        spell_def("TST-003", [], elements=["water"]),
    )
    state = make_game()
    seat = state.current
    focus, w1, w2, *_ = set_hand(state, seat, ["TST-002", "TST-003", "TST-003"] + ["MAG-S01"] * 4)
    # Condition card first: no water cards played yet, so no VP.
    after_focus, _ = apply_action(state, cat, PlayCard(seat, focus.uid))
    assert after_focus.players[seat].vp == 0
    # Two water cards first, then the condition card: +1 VP.
    s, _ = apply_action(state, cat, PlayCard(seat, w1.uid))
    s, _ = apply_action(s, cat, PlayCard(seat, w2.uid))
    s, _ = apply_action(s, cat, PlayCard(seat, focus.uid))
    assert s.players[seat].vp == 1


def test_end_turn_requires_current_player() -> None:
    state = make_game()
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), EndTurn((state.current + 1) % 2))
