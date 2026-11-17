from __future__ import annotations

import pytest

from engine.errors import IllegalAction
from engine.prompts import Prompt


def test_number_prompt_range() -> None:
    p = Prompt(kind="number", key="k", min=0, max=3)
    assert p.validate(2) == 2
    for bad in (-1, 4, "2", True, None):
        with pytest.raises(IllegalAction):
            p.validate(bad)


def test_choose_unit_and_skip() -> None:
    p = Prompt(kind="choose_unit", key="k", options=("c1", "c2"), allow_skip=True)
    assert p.validate("c2") == "c2"
    assert p.validate(None) is None
    with pytest.raises(IllegalAction):
        p.validate("c9")
    with pytest.raises(IllegalAction):
        Prompt(kind="choose_unit", key="k", options=("c1",)).validate(None)


def test_choose_card_uses_uids() -> None:
    p = Prompt(kind="choose_card", key="k", options=({"uid": "c5", "id": "MAG-S001"},))
    assert p.validate("c5") == "c5"


def test_split_damage_rules() -> None:
    p = Prompt(
        kind="split_damage", key="k", options=("a", "b", "c"), total=3, same_tier=True, tiers={"a": 1, "b": 1, "c": 2}
    )
    assert p.validate({"a": 2, "b": 1}) == {"a": 2, "b": 1}
    assert p.validate({"a": 3, "b": 0}) == {"a": 3}
    with pytest.raises(IllegalAction) as exc:
        p.validate({"a": 2, "c": 1})
    assert exc.value.key == "error.split_same_tier"
    for bad in ({"a": 2}, {"a": 4}, {"x": 3}, {"a": -1, "b": 4}, {}, "a"):
        with pytest.raises(IllegalAction):
            p.validate(bad)
