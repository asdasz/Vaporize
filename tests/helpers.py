"""Shared helpers for building games in tests."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.context import EffectContext
from engine.loader import load_catalog, parse_card
from engine.setup import new_game
from engine.state import GameState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def catalog() -> Catalog:
    return load_catalog(DATA_DIR)


def catalog_with(*raw_cards: dict[str, Any]) -> Catalog:
    """The real catalog plus test-only cards (not added to any deck)."""
    base = catalog()
    cards = dict(base.cards)
    for raw in raw_cards:
        card, errors = parse_card(raw, "test")
        assert card is not None, errors
        cards[card.id] = card
    return Catalog(cards=cards, classes=base.classes)


def spell_def(card_id: str, effects: list[dict[str, Any]], elements: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": card_id, "type": "spell", "cost": 0, "class": "mage", "source": "starter",
        "elements": elements or [], "effects": effects,
    }


def make_game(players: int = 2, seed: int = 1) -> GameState:
    state, _ = new_game(catalog(), [(f"P{i + 1}", "mage") for i in range(players)], seed)
    return state


def set_hand(state: GameState, seat: int, def_ids: list[str]) -> list[CardInstance]:
    """Replace a player's hand with fresh instances of the given cards."""
    cards = [CardInstance(uid=state.new_uid(), def_id=d, owner=seat) for d in def_ids]
    state.players[seat].hand.cards = list(cards)
    return cards


def make_cards(state: GameState, seat: int, def_ids: list[str]) -> list[CardInstance]:
    return [CardInstance(uid=state.new_uid(), def_id=d, owner=seat) for d in def_ids]


def ctx_for(state: GameState, seat: int | None = None, source: CardInstance | None = None) -> EffectContext:
    return EffectContext(state, catalog(), state.current if seat is None else seat, source, [])


def place_unit(state: GameState, seat: int, tier: int, def_id: str = "MAG-S12", hp: int = 2) -> CardInstance:
    """Put a unit straight onto the board (tier 4 = shared row)."""
    unit = CardInstance(uid=state.new_uid(), def_id=def_id, owner=seat, current_hp=hp, fixed_attack=0, fixed_health=2)
    (state.tier4 if tier == 4 else state.players[seat].tiers[tier]).place(unit)
    return unit
