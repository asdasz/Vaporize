"""Previews of number prompts (engine/preview.py): what each invoke value would do."""

from __future__ import annotations

from engine.actions import Attack, PlayCard, apply_action
from engine.view import build_view
from tests.helpers import catalog, make_game, place_unit, set_hand


def _pending_view(def_id: str, mana: int, classes: list[str] | None = None, enemy_unit: bool = False) -> dict:  # type: ignore[type-arg]
    state = make_game(classes=classes)
    seat = state.current
    if enemy_unit:
        place_unit(state, 1 - seat, 1, hp=9)
    cards = set_hand(state, seat, [def_id] + ["MAG-S001"] * 6)
    state.players[seat].resource = mana
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    assert state.pending is not None
    return build_view(state, catalog(), seat)["pending"]


def test_010_shows_vp_only_from_value_4_with_the_mage_bonus() -> None:
    pending = _pending_view("MAG-S010", mana=4)  # "if invoke is at least 4: gain 1 VP"; Mage spells +1
    previews = pending["previews"]
    assert previews["2"] == {} and previews["3"] == {"vp": 1} and previews["4"] == {"vp": 1}


def test_damage_spell_previews_the_next_question() -> None:
    previews = _pending_view("MAG-S009", mana=3, enemy_unit=True)["previews"]  # deal [invoke] damage: target prompt next
    assert previews["2"]["next"] == {"key": "prompt.deal_damage", "params": {"amount": 3, "skip_key": "ui.prompt.skip_damage"}}


def test_unit_stats_preview() -> None:
    previews = _pending_view("MON-S112", mana=6, classes=["monarch", "monarch"])["previews"]  # HP = invoke - 1 (min 1), +1
    assert previews["0"]["unit"] == [1, 2] and previews["5"]["unit"] == [1, 5]


def test_other_players_never_get_previews() -> None:
    state = make_game()
    seat = state.current
    cards = set_hand(state, seat, ["MAG-S010"] + ["MAG-S001"] * 6)
    state.players[seat].resource = 4
    state, _ = apply_action(state, catalog(), PlayCard(seat, cards[0].uid))
    assert "previews" not in build_view(state, catalog(), 1 - seat)["pending"]


def test_attack_prompt_preview_shows_damage() -> None:
    state = make_game(classes=["monarch", "mage"], seed=2)
    assert state.current == 0
    champ = place_unit(state, 0, 1, "MON-P142")
    champ.fixed_attack = 1
    target = place_unit(state, 1, 1, hp=9)
    state.players[0].resource = 4
    state, _ = apply_action(state, catalog(), Attack(0, champ.uid, target.uid))
    previews = build_view(state, catalog(), 0)["pending"]["previews"]
    assert [previews[str(n)]["damage"] for n in range(3)] == [1, 3, 5]
