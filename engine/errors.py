"""Engine exceptions."""

from __future__ import annotations

from typing import Any


class IllegalAction(Exception):
    """Raised for an action the rules don't allow. Carries a translation key."""

    def __init__(self, key: str, **params: Any) -> None:
        super().__init__(key)
        self.key = key
        self.params = params
