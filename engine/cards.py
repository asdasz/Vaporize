"""Card definitions (static, from YAML) and card instances (runtime)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.rules import STATUSES


@dataclass(frozen=True)
class CardDef:
    id: str
    type: str  # influence | spell | unit
    cost: int
    elements: tuple[str, ...]
    card_class: str  # class id, or "shared"
    source: str  # starter | private | shared
    copies: int = 1
    number: int | None = None  # printed card number ("No. 009")
    attack: int | dict[str, Any] | None = None  # int, or a value expression like {invoke: 0}
    health: int | dict[str, Any] | None = None
    effects: tuple[dict[str, Any], ...] = ()
    triggers: dict[str, tuple[dict[str, Any], ...]] = field(default_factory=dict)
    modifiers: tuple[dict[str, Any], ...] = ()  # static, while the unit is on the board

    @property
    def is_unit(self) -> bool:
        return self.type == "unit"


def _empty_status() -> dict[str, int]:
    return {name: 0 for name in STATUSES}


@dataclass
class CardInstance:
    """One physical copy of a card during a game."""

    uid: str
    def_id: str
    owner: int
    current_hp: int | None = None
    status: dict[str, int] = field(default_factory=_empty_status)
    tapped: bool = False
    fixed_attack: int | None = None
    fixed_health: int | None = None
    effective_elements: tuple[str, ...] | None = None
    is_token: bool = False
    temp_attack: int = 0  # bonus attack until the end of its owner's turn

    @property
    def attack_value(self) -> int:
        return (self.fixed_attack or 0) + self.temp_attack

    def reset_runtime(self) -> None:
        """Clear board state, e.g. when a unit leaves the board."""
        self.current_hp = None
        self.status = _empty_status()
        self.tapped = False
        self.fixed_attack = None
        self.fixed_health = None
        self.effective_elements = None
        self.temp_attack = 0
