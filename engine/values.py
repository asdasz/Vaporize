"""Value expressions used by effect params.

- an int
- {invoke: N}                                   invoke + N (never below 0)
- {count: {played: {element: fire, other: true}}}   cards played this turn with that element
- {count: {unique_played_elements: {other: true}}}  different elements on cards played this turn
- {sum: [v1, v2, ...]}
"""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.invoke import invoke
from engine.rules import ELEMENTS

COUNTERS = {"played": {"element", "other"}, "unique_played_elements": {"other"}}


def validate_value(value: Any, where: str) -> list[str]:
    if isinstance(value, bool):
        return [f"{where}: expected a number or a value expression"]
    if isinstance(value, int):
        return []
    if isinstance(value, dict) and len(value) == 1:
        (kind, arg), = value.items()
        if kind == "invoke" and isinstance(arg, int) and not isinstance(arg, bool):
            return []
        if kind == "sum" and isinstance(arg, list) and arg:
            return [e for i, v in enumerate(arg) for e in validate_value(v, f"{where}.sum[{i}]")]
        if kind == "count" and isinstance(arg, dict) and len(arg) == 1:
            (counter, params), = arg.items()
            if counter not in COUNTERS or not isinstance(params, dict):
                return [f"{where}: unknown counter {counter!r}"]
            errors = [f"{where}.count.{counter}: unknown param {k!r}" for k in sorted(params.keys() - COUNTERS[counter])]
            if "element" in params and params["element"] not in ELEMENTS:
                errors.append(f"{where}.count.{counter}: unknown element {params['element']!r}")
            return errors
    return [f"{where}: expected an int, {{invoke: N}}, {{count: …}} or {{sum: […]}}, got {value!r}"]


def _played(ctx: EffectContext, other: bool) -> list[tuple[str, ...]]:
    source_uid = ctx.source.uid if ctx.source else None
    return [p.elements for p in ctx.player.played_this_turn if not (other and p.uid == source_uid)]


def _count(ctx: EffectContext, counter: str, params: dict[str, Any]) -> int:
    other = bool(params.get("other"))
    if counter == "played":
        return sum(1 for els in _played(ctx, other) if params["element"] in els)
    if counter == "unique_played_elements":
        return len({e for els in _played(ctx, other) for e in els})
    raise ValueError(f"unknown counter {counter!r}")


def resolve_value(ctx: EffectContext, value: Any) -> int:
    if isinstance(value, int):
        return value
    (kind, arg), = value.items()
    if kind == "invoke":
        return max(0, invoke(ctx) + int(arg))
    if kind == "sum":
        return sum(resolve_value(ctx, v) for v in arg)
    if kind == "count":
        (counter, params), = arg.items()
        return _count(ctx, counter, params)
    raise ValueError(f"unsupported value expression {value!r}")
