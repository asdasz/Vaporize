"""Class (character board) definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResourceRule:
    key: str  # mana, heat, ...
    start: int = 0
    limit: int | None = None  # cap for passive / prepare gains
    hard_max: int | None = None  # absolute cap, reachable by card effects only


@dataclass(frozen=True)
class TierRule:
    spots: int | None  # None for tier 4 (players - 1, shared)
    develop_cost: int | None
    vp: int


@dataclass(frozen=True)
class ClassDef:
    id: str
    primary_elements: tuple[str, ...]
    resource: ResourceRule
    tiers: dict[int, TierRule]
    removal_costs: tuple[int, ...]
    passives: tuple[dict[str, Any], ...] = ()
    prepare: tuple[dict[str, Any], ...] = ()
    invoke: dict[str, Any] = field(default_factory=dict)

    def removal_cost(self, index: int) -> int | None:
        """Cost of the next removal, or None when the track is exhausted."""
        if 0 <= index < len(self.removal_costs):
            return self.removal_costs[index]
        return None
