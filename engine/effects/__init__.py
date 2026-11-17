"""Importing this package registers every effect primitive."""

from engine.effects import cards, class_hooks, damage, keywords, resources  # noqa: F401
from engine.effects.registry import get_effect, registered_effects, validate_effects

__all__ = ["get_effect", "registered_effects", "validate_effects"]
