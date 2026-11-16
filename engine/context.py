"""Context passed to every effect primitive."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.classes import ClassDef
from engine.events import Event
from engine.state import GameState, PlayerState


@dataclass
class EffectContext:
    state: GameState
    catalog: Catalog
    seat: int  # player who controls the effect
    source: CardInstance | None  # card that produced the effect (None for class passives)
    events: list[Event]

    @property
    def player(self) -> PlayerState:
        return self.state.players[self.seat]

    @property
    def class_def(self) -> ClassDef:
        return self.catalog.cls(self.player.class_id)

    def emit(self, key: str, **params: Any) -> None:
        self.events.append(Event(key, params))
