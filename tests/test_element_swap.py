from __future__ import annotations

import pytest

from engine.actions import EndTurn, IllegalAction, PlayCard, Respond, Undo, apply_action
from engine.element_swap import swap_options
from engine.view import build_view
from tests.helpers import catalog, make_cards, make_game, set_hand


def test_options_single_double_all_and_none() -> None:
    state = make_game()
    fire, water_shadow, everything = make_cards(state, 0, ["MAG-S001", "MAG-S010", "MAG-P035"])
    assert swap_options(catalog(), fire) == {"fire": ["water", "wind", "lightning", "shadow"]}
    both = swap_options(catalog(), water_shadow)
    assert both == {"water": ["fire", "wind", "lightning"], "shadow": ["fire", "wind", "lightning"]}
    assert swap_options(catalog(), everything) is None  # "all" can't change
    no_element = make_cards(state, 0, ["MAG-P039"])[0]
    assert swap_options(catalog(), no_element) is None


def test_swap_changes_played_elements_and_is_free() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001", *["MAG-S002"] * 6])
    state, events = apply_action(state, catalog(), PlayCard(seat, cards[0].uid, ("fire", "water")))
    p = state.players[seat]
    assert p.played_this_turn[0].elements == ("water",)
    assert p.inf == 1 and p.element_swap_used
    assert events[0].key == "log.element_swapped"
    assert build_view(state, catalog(), seat)["players"][seat]["played_elements"]["water"] == 1


def test_swap_counts_for_conditions() -> None:
    state = make_game()
    seat = state.current
    # 3 water cards for 009's split: two water influences + one fire influence swapped to water
    cards = set_hand(state, seat, ["MAG-S006", "MAG-S007", "MAG-S001", "MAG-S009", *["MAG-S002"] * 3])
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[1].uid))
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[2].uid, ("fire", "water")))
    from tests.helpers import place_unit

    place_unit(state, (seat + 1) % 2, 1)
    state.players[seat].resource = 0
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[3].uid))
    assert state.pending.prompt.kind == "split_damage"


def test_only_once_per_turn() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001", "MAG-S002", *["MAG-S003"] * 5])
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid, ("fire", "wind")))
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), PlayCard(seat, cards[1].uid, ("fire", "wind")))
    assert exc.value.key == "error.swap_used"
    assert build_view(state, catalog(), seat)["legal"]["element_swap"]["available"] is False


def test_no_duplicates_and_no_all() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S010", "MAG-P035", *["MAG-S001"] * 5])
    for swap in (("water", "shadow"), ("water", "all"), ("fire", "wind")):
        with pytest.raises(IllegalAction) as exc:
            apply_action(state, catalog(), PlayCard(seat, cards[0].uid, swap))
        assert exc.value.key == "error.swap_invalid"
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), PlayCard(seat, cards[1].uid, ("fire", "water")))  # all-element card


def test_swap_survives_prompts_and_undo_restores_it() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S010", *["MAG-S001"] * 6])
    state.players[seat].resource = 3
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid, ("shadow", "fire")))
    assert state.pending is not None and state.pending.swap == ("shadow", "fire")
    state, _ = apply_action(state, catalog(), Respond(seat, 3))
    p = state.players[seat]
    assert p.played_this_turn[0].elements == ("water", "fire") and p.element_swap_used and p.vp == 1
    state, _ = apply_action(state, catalog(), Undo(seat))
    assert not state.players[seat].element_swap_used


def test_swap_resets_next_turn_and_card_goes_back_to_printed() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001", *["MAG-S002"] * 6])
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid, ("fire", "shadow")))
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    p = state.players[seat]
    card = p.discard.find(cards[0].uid) or p.hand.find(cards[0].uid) or p.deck.find(cards[0].uid)
    assert card is not None and card.effective_elements is None
    state, _ = apply_action(state, catalog(), EndTurn(state.current))
    assert state.players[seat].element_swap_used is False


def test_view_lists_swap_options_for_hand() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S001", "MAG-P035", *["MAG-S002"] * 5])
    swap = build_view(state, catalog(), seat)["legal"]["element_swap"]
    assert swap["has"] and swap["available"]
    assert cards[0].uid in swap["options"] and cards[1].uid not in swap["options"]
