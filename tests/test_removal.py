from __future__ import annotations

import pytest

from engine.actions import IllegalAction, PlayCard, RemoveCard, Undo, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_cards, make_game, set_hand


def _remove(state: GameState, seat: int, uid: str) -> GameState:
    return apply_action(state, catalog(), RemoveCard(seat, uid))[0]


def _game_with_discard(inf: int = 10) -> tuple[GameState, int, list[str]]:
    state = make_game()
    seat = state.current
    cards = make_cards(state, seat, ["MAG-S002", "MAG-S005", "MAG-S006", "MAG-S007"])
    state.players[seat].discard.cards = list(cards)
    state.players[seat].inf = inf
    return state, seat, [c.uid for c in cards]


def test_remove_from_discard_pays_track_cost_1_1_2_2() -> None:
    state, seat, uids = _game_with_discard(inf=10)
    for uid, inf_left in zip(uids, (9, 8, 6, 4)):
        state = _remove(state, seat, uid)
        assert state.players[seat].inf == inf_left
    p = state.players[seat]
    assert p.discard.is_empty() and [c.uid for c in p.removed] == uids
    assert p.removal_index == 4
    assert build_view(state, catalog(), seat)["players"][seat]["removal_cost"] == 3


def test_removing_a_played_card_keeps_its_effects() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S006", "MAG-S007", *["MAG-S001"] * 5])  # two water influences
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[1].uid))
    assert state.players[seat].inf == 2
    state = _remove(state, seat, cards[0].uid)  # costs 1
    p = state.players[seat]
    assert p.inf == 1  # the removed card's +1 inf stays; only the cost is paid
    assert p.in_play.find(cards[0].uid) is None and p.removed.find(cards[0].uid) is not None
    assert build_view(state, catalog(), seat)["players"][seat]["played_elements"]["water"] == 2


def test_cannot_remove_from_deck() -> None:
    state, seat, _ = _game_with_discard()
    with pytest.raises(IllegalAction) as exc:
        _remove(state, seat, state.players[seat].deck.cards[0].uid)
    assert exc.value.key == "error.card_not_removable"


def test_remove_from_hand_keeps_two_cards() -> None:
    state, seat, _ = _game_with_discard(inf=99)
    hand = [c.uid for c in state.players[seat].hand]
    for uid in hand[:5]:
        state = _remove(state, seat, uid)
    p = state.players[seat]
    assert len(p.hand) == 2 and all(p.removed.find(uid) for uid in hand[:5])
    assert not set(build_view(state, catalog(), seat)["legal"]["removable"]) & set(hand)
    with pytest.raises(IllegalAction) as exc:
        _remove(state, seat, hand[5])
    assert exc.value.key == "error.min_hand"


def test_removed_hand_card_does_not_count_as_played() -> None:
    state, seat, _ = _game_with_discard(inf=1)
    uid = state.players[seat].hand.cards[0].uid
    state = _remove(state, seat, uid)
    p = state.players[seat]
    assert p.played_this_turn == [] and p.inf == 0


def test_remove_needs_enough_inf() -> None:
    state, seat, uids = _game_with_discard(inf=0)
    with pytest.raises(IllegalAction) as exc:
        _remove(state, seat, uids[0])
    assert exc.value.key == "error.not_enough_inf" and exc.value.params == {"cost": 1}


def test_removal_track_can_run_out() -> None:
    state, seat, uids = _game_with_discard(inf=99)
    state.players[seat].removal_index = len(catalog().cls("mage").removal_costs)
    with pytest.raises(IllegalAction) as exc:
        _remove(state, seat, uids[0])
    assert exc.value.key == "error.removal_track_full"


def test_remove_only_on_your_turn() -> None:
    state, seat, uids = _game_with_discard()
    with pytest.raises(IllegalAction) as exc:
        _remove(state, (seat + 1) % 2, uids[0])
    assert exc.value.key == "error.not_your_turn"


def test_remove_can_be_undone() -> None:
    state, seat, uids = _game_with_discard(inf=3)
    state = _remove(state, seat, uids[0])
    state, _ = apply_action(state, catalog(), Undo(seat))
    p = state.players[seat]
    assert p.inf == 3 and p.removal_index == 0 and p.discard.find(uids[0]) is not None


def test_view_lists_removable_cards_and_removed_pile() -> None:
    state, seat, uids = _game_with_discard(inf=1)
    legal = build_view(state, catalog(), seat)["legal"]
    hand = {c.uid for c in state.players[seat].hand}
    assert set(legal["removable"]) == set(uids) | hand
    state = _remove(state, seat, uids[0])
    view = build_view(state, catalog(), seat)
    assert view["legal"]["removable"] == []  # next removal costs 1 more than the 0 inf left
    assert [c["uid"] for c in view["players"][seat]["removed"]] == [uids[0]]
