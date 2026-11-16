from __future__ import annotations

import json

from engine.loader import parse_card
from engine.rules import KEYWORDS
from tests.helpers import DATA_DIR, catalog


def test_catalog_loads_all_data() -> None:
    cat = catalog()
    assert "mage" in cat.classes
    assert cat.cards


def test_mage_starter_deck_has_12_cards() -> None:
    assert sum(c.copies for c in catalog().starter_cards("mage")) == 12


def _locale(name: str) -> dict:
    return json.loads((DATA_DIR / "locales" / "en" / f"{name}.json").read_text(encoding="utf-8"))


def test_every_card_has_english_name_and_text() -> None:
    cards = _locale("cards")
    for card_id in catalog().cards:
        assert card_id in cards, f"missing locale entry for {card_id}"
        assert cards[card_id].get("name") and "text" in cards[card_id]


def test_every_class_and_keyword_has_english_entry() -> None:
    classes, keywords = _locale("classes"), _locale("keywords")
    for class_id in catalog().classes:
        assert classes.get(class_id, {}).get("name"), f"missing locale for class {class_id}"
    for kw in KEYWORDS:
        assert keywords.get(kw, {}).get("name"), f"missing locale for keyword {kw}"


def test_parse_card_rejects_unknown_effect() -> None:
    raw = {
        "id": "MAG-S99", "type": "spell", "cost": 0, "class": "mage", "source": "starter",
        "effects": [{"do": "teleport"}],
    }
    card, errors = parse_card(raw, "test")
    assert card is None
    assert any("unknown effect" in e for e in errors)


def test_parse_card_rejects_missing_param_and_bad_element() -> None:
    raw = {
        "id": "MAG-S99", "type": "influence", "cost": 0, "class": "mage", "source": "starter",
        "elements": ["ice"], "effects": [{"do": "gain_inf"}],
    }
    _, errors = parse_card(raw, "test")
    assert any("missing 'amount'" in e for e in errors)
    assert any("elements" in e for e in errors)


def test_parse_card_expands_all_elements() -> None:
    raw = {"id": "SHR-001", "type": "spell", "cost": 2, "class": "shared", "source": "shared", "elements": ["all"]}
    card, errors = parse_card(raw, "test")
    assert not errors and card is not None
    assert len(card.elements) == 5


def test_unit_requires_stats() -> None:
    raw = {"id": "MAG-S99", "type": "unit", "cost": 0, "class": "mage", "source": "starter"}
    _, errors = parse_card(raw, "test")
    assert any("attack" in e for e in errors)
