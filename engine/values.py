"""Value expressions used by effect params: an int, or {invoke: N} meaning invoke + N."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.invoke import invoke


def validate_value(value: Any, where: str) -> list[str]:
    if isinstance(value, bool):
        return [f"{where}: expected a number or a value expression"]
    if isinstance(value, int):
        return []
    if isinstance(value, dict) and len(value) == 1 and "invoke" in value and isinstance(value["invoke"], int):
        return []
    return [f"{where}: expected an int or {{invoke: N}}, got {value!r}"]


def resolve_value(ctx: EffectContext, value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and "invoke" in value:
        return max(0, invoke(ctx) + int(value["invoke"]))
    raise ValueError(f"unsupported value expression {value!r}")
