"""Events describe what happened. They carry a translation key + params, never display text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    key: str  # e.g. "log.card_played"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "params": dict(self.params)}
