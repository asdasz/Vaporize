"""Card piles. Every pile in the game is an explicit Zone or SlotRow."""

from __future__ import annotations

import random
from collections.abc import Iterator

from engine.cards import CardInstance


class Zone:
    """Ordered pile of cards. Index 0 is the top."""

    def __init__(self, name: str, cards: list[CardInstance] | None = None) -> None:
        self.name = name
        self.cards: list[CardInstance] = list(cards) if cards else []

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[CardInstance]:
        return iter(self.cards)

    def __repr__(self) -> str:
        return f"Zone({self.name!r}, {len(self.cards)} cards)"

    def is_empty(self) -> bool:
        return not self.cards

    def top(self) -> CardInstance | None:
        return self.cards[0] if self.cards else None

    def draw(self) -> CardInstance:
        if not self.cards:
            raise IndexError(f"zone {self.name!r} is empty")
        return self.cards.pop(0)

    def put_top(self, card: CardInstance) -> None:
        self.cards.insert(0, card)

    def put_bottom(self, card: CardInstance) -> None:
        self.cards.append(card)

    def find(self, uid: str) -> CardInstance | None:
        return next((c for c in self.cards if c.uid == uid), None)

    def take(self, uid: str) -> CardInstance:
        for i, card in enumerate(self.cards):
            if card.uid == uid:
                return self.cards.pop(i)
        raise KeyError(f"card {uid!r} not in zone {self.name!r}")

    def take_all(self) -> list[CardInstance]:
        cards, self.cards = self.cards, []
        return cards

    def shuffle(self, rng: random.Random) -> None:
        rng.shuffle(self.cards)


class SlotRow:
    """Fixed number of slots (market rows, unit tiers). Empty slot = None."""

    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self.slots: list[CardInstance | None] = [None] * size

    def __len__(self) -> int:
        return len(self.slots)

    def __repr__(self) -> str:
        return f"SlotRow({self.name!r}, {len(self.cards())}/{len(self.slots)})"

    def cards(self) -> list[CardInstance]:
        return [c for c in self.slots if c is not None]

    def free_index(self) -> int | None:
        return next((i for i, c in enumerate(self.slots) if c is None), None)

    def has_free(self) -> bool:
        return self.free_index() is not None

    def place(self, card: CardInstance, index: int | None = None) -> int:
        if index is None:
            index = self.free_index()
            if index is None:
                raise ValueError(f"no free slot in {self.name!r}")
        elif self.slots[index] is not None:
            raise ValueError(f"slot {index} in {self.name!r} is occupied")
        self.slots[index] = card
        return index

    def find(self, uid: str) -> CardInstance | None:
        return next((c for c in self.slots if c is not None and c.uid == uid), None)

    def take(self, uid: str) -> CardInstance:
        for i, card in enumerate(self.slots):
            if card is not None and card.uid == uid:
                self.slots[i] = None
                return card
        raise KeyError(f"card {uid!r} not in {self.name!r}")
