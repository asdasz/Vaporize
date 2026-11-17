"""Context passed to every effect primitive."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.classes import ClassDef
from engine.events import Event
from engine.prompts import NeedChoice, Prompt
from engine.state import GameState, PlayerState


@dataclass
class EffectContext:
    state: GameState
    catalog: Catalog
    seat: int  # player who controls the effect
    source: CardInstance | None  # card that produced the effect (None for class passives)
    events: list[Event]
    answers: list[Any] = field(default_factory=list)  # player's answers to prompts, in order
    answer_index: int = 0
    invoke_value: int | None = None  # a card invokes once; later uses reuse the value
    keywords: dict[str, dict[str, Any]] = field(default_factory=dict)  # granted while this card resolves

    @property
    def player(self) -> PlayerState:
        return self.state.players[self.seat]

    @property
    def class_def(self) -> ClassDef:
        return self.catalog.cls(self.player.class_id)

    def emit(self, key: str, **params: Any) -> None:
        self.events.append(Event(key, params))

    def ask(self, prompt: Prompt) -> Any:
        """Return the player's answer to `prompt`, or raise NeedChoice if it hasn't been given yet."""
        if prompt.kind == "number" and prompt.min == prompt.max:
            return prompt.min  # only one possible answer: don't ask
        if self.answer_index < len(self.answers):
            answer = prompt.validate(self.answers[self.answer_index])
            self.answer_index += 1
            return answer
        raise NeedChoice(prompt)
