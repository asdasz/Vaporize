"""Choices the engine asks a player to make while a card resolves.

Resolution is replayed from the state before the card was played, feeding the answers
given so far. When an effect needs an answer that isn't there yet, it raises `NeedChoice`;
the engine stores the prompt as `state.pending` and waits for a `Respond` action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.errors import IllegalAction

PROMPT_KINDS = ("number", "choose_unit", "choose_card", "split_damage")


@dataclass(frozen=True)
class Prompt:
    kind: str  # one of PROMPT_KINDS
    key: str  # translation key, e.g. "prompt.invoke"
    params: dict[str, Any] = field(default_factory=dict)
    options: tuple[Any, ...] = ()  # unit uids (choose_unit, split_damage) or card dicts (choose_card)
    min: int = 0  # number
    max: int = 0  # number
    total: int = 0  # split_damage: damage to assign
    same_tier: bool = False  # split_damage: all targets on one tier
    tiers: dict[str, int] = field(default_factory=dict)  # split_damage: uid -> tier
    allow_skip: bool = False  # answer None skips an optional effect
    cancellable: bool = True  # False once hidden information has been shown (e.g. scout)

    def option_ids(self) -> list[str]:
        if self.kind == "choose_card":
            return [str(o["uid"]) for o in self.options]
        return [str(o) for o in self.options]

    def validate(self, answer: Any) -> Any:
        """Return the normalised answer or raise IllegalAction."""
        if answer is None:
            if self.allow_skip:
                return None
            raise IllegalAction("error.invalid_choice")
        if self.kind == "number":
            if isinstance(answer, bool) or not isinstance(answer, int) or not self.min <= answer <= self.max:
                raise IllegalAction("error.invalid_choice")
            return answer
        if self.kind in ("choose_unit", "choose_card"):
            if str(answer) not in self.option_ids():
                raise IllegalAction("error.invalid_choice")
            return str(answer)
        if self.kind == "split_damage":
            return self._validate_split(answer)
        raise IllegalAction("error.invalid_choice")

    def _validate_split(self, answer: Any) -> dict[str, int]:
        if not isinstance(answer, dict) or not answer:
            raise IllegalAction("error.invalid_choice")
        options = set(self.option_ids())
        result: dict[str, int] = {}
        for uid, amount in answer.items():
            if str(uid) not in options or isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise IllegalAction("error.invalid_choice")
            if amount:
                result[str(uid)] = amount
        if sum(result.values()) != self.total or not result:
            raise IllegalAction("error.invalid_choice")
        if self.same_tier and len({self.tiers[uid] for uid in result}) > 1:
            raise IllegalAction("error.split_same_tier")
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "key": self.key,
            "params": dict(self.params),
            "options": list(self.options),
            "min": self.min,
            "max": self.max,
            "total": self.total,
            "same_tier": self.same_tier,
            "tiers": dict(self.tiers),
            "allow_skip": self.allow_skip,
            "cancellable": self.cancellable,
        }


class NeedChoice(Exception):
    """Raised by an effect that needs an answer the player hasn't given yet."""

    def __init__(self, prompt: Prompt) -> None:
        super().__init__(prompt.key)
        self.prompt = prompt


@dataclass
class PendingChoice:
    """A card waiting for the player's answer. The state itself is from before the card was played."""

    seat: int
    card_uid: str
    answers: list[Any]
    prompt: Prompt
