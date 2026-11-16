"""All static game data (cards + classes), loaded once and shared read-only."""

from __future__ import annotations

from dataclasses import dataclass

from engine.cards import CardDef
from engine.classes import ClassDef


@dataclass(frozen=True)
class Catalog:
    cards: dict[str, CardDef]
    classes: dict[str, ClassDef]

    def card(self, card_id: str) -> CardDef:
        return self.cards[card_id]

    def cls(self, class_id: str) -> ClassDef:
        return self.classes[class_id]

    def _select(self, card_class: str, source: str) -> list[CardDef]:
        return sorted(
            (c for c in self.cards.values() if c.card_class == card_class and c.source == source),
            key=lambda c: c.id,
        )

    def starter_cards(self, class_id: str) -> list[CardDef]:
        return self._select(class_id, "starter")

    def private_cards(self, class_id: str) -> list[CardDef]:
        return self._select(class_id, "private")

    def shared_cards(self) -> list[CardDef]:
        return self._select("shared", "shared")
