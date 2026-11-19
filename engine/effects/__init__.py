"""Importing this package registers every effect primitive."""

from engine.effects import (  # noqa: F401
    cards,
    class_hooks,
    damage,
    economy,
    keywords,
    market_effects,
    modifiers,
    movement,
    resources,
    status,
)
from engine.effects.registry import get_effect, registered_effects, validate_effects

__all__ = ["get_effect", "registered_effects", "validate_effects"]
