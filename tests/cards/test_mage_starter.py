"""End-to-end behaviour of the Mage starter cards (001-012)."""

from __future__ import annotations

from typing import Any

import pytest

from engine.actions import CancelChoice, EndTurn, IllegalAction, PlayCard, Respond, Undo, apply_action
from engine.state import GameState
from engine.view import build_view
from tests.helpers import catalog, make_cards, make_game, place_unit, set_hand

FILLER = ["MAG-S01"] * 6


def _setup(card_id: str, mana: int = 3) -> tuple[GameState, int, str]:
    state = make_game()
    seat = state.current
    card = set_hand(state, seat, [card_id, *FILLER])[0]
    state.players[seat].resource = mana
    return state, seat, card.uid


def _play(state: GameState, seat: int, uid: str, *answers: Any) -> GameState:
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    for answer in answers:
        assert state.pending is not None, "expected a prompt"
        state, _ = apply_action(state, catalog(), Respond(seat, answer))
    return state


def test_starter_deck_is_the_12_numbered_cards() -> None:
    starters = catalog().starter_cards("mage")
    assert [c.number for c in starters] == list(range(1, 13))
    assert all(c.copies == 1 for c in starters)


def test_008_scout_invoke_minus_one_and_draw_one() -> None:
    state, seat, uid = _setup("MAG-S08", mana=3)
    p = state.players[seat]
    p.deck.cards = make_cards(state, seat, ["MAG-S05", "MAG-S06", "MAG-S07", "MAG-S09", "MAG-S10"])
    top = [c.uid for c in p.deck]
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    state, _ = apply_action(state, catalog(), Respond(seat, 2))  # spend 2 mana -> value 3 -> scout 2
    prompt = state.pending.prompt
    assert prompt.kind == "choose_card" and [o["uid"] for o in prompt.options] == top[:2]
    state, _ = apply_action(state, catalog(), Respond(seat, top[1]))
    p = state.players[seat]
    assert p.hand.find(top[1]) is not None
    assert [c.uid for c in p.deck][:1] == [top[0]]
    assert p.resource == 1
    assert state.undo_stack == []  # scouting revealed cards: can't undo


def test_008_scout_cannot_be_cancelled_after_reveal() -> None:
    state, seat, uid = _setup("MAG-S08", mana=2)
    state = _play(state, seat, uid, 2)
    with pytest.raises(IllegalAction) as exc:
        apply_action(state, catalog(), CancelChoice(seat))
    assert exc.value.key == "error.choice_not_cancellable"


def test_009_deals_invoke_damage_to_one_unit() -> None:
    state, seat, uid = _setup("MAG-S09", mana=3)
    enemy = (seat + 1) % 2
    target = place_unit(state, enemy, 2, hp=5)
    state = _play(state, seat, uid, 3, target.uid)  # 3 mana + 1 bonus = 4 damage
    unit = next(u for _, u in state.units_of(enemy) if u.uid == target.uid)
    assert unit.current_hp == 1


def test_009_split_after_three_water_cards_single_tier() -> None:
    state = make_game()
    seat = state.current
    enemy = (seat + 1) % 2
    water = ["MAG-S06", "MAG-S07", "MAG-S12"]
    cards = set_hand(state, seat, [*water, "MAG-S09", "MAG-S01", "MAG-S01", "MAG-S01"])
    state.players[seat].resource = 2
    a = place_unit(state, enemy, 1, hp=2)
    b = place_unit(state, enemy, 1, hp=2)
    c = place_unit(state, enemy, 2, hp=2)
    for card in cards[:3]:
        state = _play(state, seat, card.uid)
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[3].uid))
    state, _ = apply_action(state, catalog(), Respond(seat, 2))  # value 3
    assert state.pending.prompt.kind == "split_damage"
    with pytest.raises(IllegalAction):
        apply_action(state, catalog(), Respond(seat, {a.uid: 2, c.uid: 1}))  # two tiers
    state, _ = apply_action(state, catalog(), Respond(seat, {a.uid: 2, b.uid: 1}))
    alive = {u.uid: u.current_hp for _, u in state.units_of(enemy)}
    assert a.uid not in alive and alive[b.uid] == 1 and alive[c.uid] == 2


def test_009_no_split_with_only_two_water_cards() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S06", "MAG-S07", "MAG-S09", *["MAG-S01"] * 4])
    place_unit(state, (seat + 1) % 2, 1)
    for card in cards[:2]:
        state = _play(state, seat, card.uid)
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[2].uid))
    state, _ = apply_action(state, catalog(), Respond(seat, 0))
    assert state.pending.prompt.kind == "choose_unit"


def test_010_invoke_for_4_gains_vp() -> None:
    for spent, vp in ((3, 1), (2, 0), (4, 1)):
        state, seat, uid = _setup("MAG-S10", mana=4)
        state = _play(state, seat, uid, spent)
        assert state.players[seat].vp == vp, spent
        assert state.players[seat].resource == 4 - spent


def test_011_heal_capped_at_six() -> None:
    state, seat, uid = _setup("MAG-S11", mana=4)
    unit = place_unit(state, seat, 1, hp=3)
    state = _play(state, seat, uid, 4, unit.uid)  # value 5 -> +4 HP, capped at 6
    healed = next(u for _, u in state.units_of(seat) if u.uid == unit.uid)
    assert healed.current_hp == 6


def test_012_apprentice_prepares_at_start_of_turn() -> None:
    state, seat, uid = _setup("MAG-S12", mana=0)
    state = _play(state, seat, uid)
    assert state.players[seat].tiers[1].cards()[0].current_hp == 2
    state, _ = apply_action(state, catalog(), EndTurn(seat))
    state, _ = apply_action(state, catalog(), EndTurn(state.current))
    # Back to seat: lost 3 at EOT (0 -> 0), then SOT +3 and prepare +1 = 4 (limit).
    assert state.current == seat and state.players[seat].resource == 4


def test_pending_choice_blocks_other_actions_and_can_be_cancelled() -> None:
    state, seat, uid = _setup("MAG-S10", mana=3)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    assert state.players[seat].hand.find(uid) is not None  # card stays in hand until resolved
    for action in (EndTurn(seat), Undo(seat), PlayCard(seat, state.players[seat].hand.cards[1].uid)):
        with pytest.raises(IllegalAction) as exc:
            apply_action(state, catalog(), action)
        assert exc.value.key == "error.choice_pending"
    state, events = apply_action(state, catalog(), CancelChoice(seat))
    assert state.pending is None and state.players[seat].resource == 3
    assert events[0].key == "log.play_cancelled"


def test_resolved_card_can_be_undone() -> None:
    state, seat, uid = _setup("MAG-S10", mana=3)
    state = _play(state, seat, uid, 3)
    assert state.players[seat].vp == 1
    state, _ = apply_action(state, catalog(), Undo(seat))
    assert state.players[seat].vp == 0 and state.players[seat].resource == 3


def test_prompt_is_only_shown_to_the_acting_player() -> None:
    state, seat, uid = _setup("MAG-S10", mana=3)
    state, _ = apply_action(state, catalog(), PlayCard(seat, uid))
    mine = build_view(state, catalog(), seat)["pending"]
    theirs = build_view(state, catalog(), (seat + 1) % 2)["pending"]
    assert mine["prompt"]["kind"] == "number" and mine["card"]["id"] == "MAG-S10"
    assert "prompt" not in theirs and theirs["seat"] == seat
    assert build_view(state, catalog(), seat)["legal"]["playable"] == []
