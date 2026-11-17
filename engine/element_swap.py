"""Mage passive: once per turn, when you play a card, treat one of its printed elements as another.

Rules (Jan's ruling):
- free, once per turn, chosen when the card is played;
- the card must have 1 or 2 printed elements: cards with no element or with all five can't change;
- the new element is a single element that the card doesn't already have (no duplicates, never "all").
"""

from __future__ import annotations

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.rules import ELEMENTS
from engine.state import GameState

MODIFIER = "element_swap_once_per_turn"


def has_element_swap(state: GameState, catalog: Catalog, seat: int) -> bool:
    cdef = catalog.cls(state.players[seat].class_id)
    return any(p.get("modifier") == MODIFIER for p in cdef.passives)


def swap_options(catalog: Catalog, card: CardInstance) -> dict[str, list[str]] | None:
    """{from_element: [possible new elements]} for this card, or None if it can't change."""
    printed = catalog.card(card.def_id).elements
    if not printed or len(printed) >= len(ELEMENTS):
        return None
    targets = [e for e in ELEMENTS if e not in printed]
    return {e: targets for e in printed}


def swap_available(state: GameState, catalog: Catalog, seat: int) -> bool:
    return has_element_swap(state, catalog, seat) and not state.players[seat].element_swap_used


def check_swap(state: GameState, catalog: Catalog, seat: int, card: CardInstance, swap: tuple[str, str]) -> None:
    if not has_element_swap(state, catalog, seat):
        raise IllegalAction("error.swap_not_allowed")
    if state.players[seat].element_swap_used:
        raise IllegalAction("error.swap_used")
    options = swap_options(catalog, card)
    old, new = swap
    if options is None or old not in options or new not in options[old]:
        raise IllegalAction("error.swap_invalid")


def swapped_elements(catalog: Catalog, card: CardInstance, swap: tuple[str, str]) -> tuple[str, ...]:
    old, new = swap
    return tuple(new if e == old else e for e in catalog.card(card.def_id).elements)
