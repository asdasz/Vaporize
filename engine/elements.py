"""Element helpers."""

from __future__ import annotations

from engine.cards import CardInstance
from engine.catalog import Catalog


def elements_of(card: CardInstance, catalog: Catalog) -> tuple[str, ...]:
    """Current elements of a card instance (respects the Mage element swap)."""
    if card.effective_elements is not None:
        return card.effective_elements
    return catalog.card(card.def_id).elements
