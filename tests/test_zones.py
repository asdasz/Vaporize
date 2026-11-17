from __future__ import annotations

import random

import pytest

from engine.cards import CardInstance
from engine.zones import SlotRow, Zone


def _cards(n: int) -> list[CardInstance]:
    return [CardInstance(uid=f"u{i}", def_id="MAG-S001", owner=0) for i in range(n)]


def test_zone_draw_takes_from_top() -> None:
    zone = Zone("deck", _cards(3))
    assert zone.draw().uid == "u0"
    assert len(zone) == 2


def test_zone_draw_empty_raises() -> None:
    with pytest.raises(IndexError):
        Zone("deck").draw()


def test_zone_take_and_find() -> None:
    zone = Zone("hand", _cards(3))
    assert zone.find("u1") is not None
    assert zone.take("u1").uid == "u1"
    assert zone.find("u1") is None
    with pytest.raises(KeyError):
        zone.take("u1")


def test_zone_put_top_bottom_and_take_all() -> None:
    zone = Zone("pile", _cards(1))
    a, b = _cards(3)[1:]
    zone.put_top(a)
    zone.put_bottom(b)
    assert [c.uid for c in zone] == ["u1", "u0", "u2"]
    assert len(zone.take_all()) == 3
    assert zone.is_empty()


def test_zone_shuffle_is_deterministic_per_seed() -> None:
    z1, z2 = Zone("a", _cards(10)), Zone("b", _cards(10))
    z1.shuffle(random.Random(5))
    z2.shuffle(random.Random(5))
    assert [c.uid for c in z1] == [c.uid for c in z2]


def test_slot_row_place_and_take() -> None:
    row = SlotRow("tier1", 2)
    a, b, c = _cards(3)
    assert row.place(a) == 0
    assert row.place(b) == 1
    assert not row.has_free()
    with pytest.raises(ValueError):
        row.place(c)
    row.take("u0")
    assert row.free_index() == 0
    assert [x.uid for x in row.cards()] == ["u1"]
