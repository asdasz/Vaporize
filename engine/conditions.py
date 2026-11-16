"""Conditions used by `if:` blocks in card effects."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from engine.context import EffectContext
from engine.elements import elements_of
from engine.rules import ELEMENTS

ConditionFn = Callable[[EffectContext, dict[str, Any]], bool]


def _played_this_turn(ctx: EffectContext, p: dict[str, Any]) -> bool:
    """Counts cards played earlier this turn (plus this one unless `other: true`)."""
    source_uid = ctx.source.uid if ctx.source else None
    count = sum(
        1
        for played in ctx.player.played_this_turn
        if p["element"] in played.elements and not (p.get("other") and played.uid == source_uid)
    )
    return count >= p["min"]


def _in_discard(ctx: EffectContext, p: dict[str, Any]) -> bool:
    """Discard pile includes the cards played this turn (rulebook)."""
    cards = list(ctx.player.discard) + list(ctx.player.in_play)
    count = sum(1 for c in cards if p["element"] in elements_of(c, ctx.catalog))
    return count >= p["min"]


# name -> (function, required params, optional params)
_CONDITIONS: dict[str, tuple[ConditionFn, frozenset[str], frozenset[str]]] = {
    "played_this_turn": (_played_this_turn, frozenset({"element", "min"}), frozenset({"other"})),
    "in_discard": (_in_discard, frozenset({"element", "min"}), frozenset()),
}


def validate_condition(cond: Any, where: str) -> list[str]:
    if not isinstance(cond, dict) or len(cond) != 1:
        return [f"{where}: condition must be a mapping with exactly one key"]
    (name, params), = cond.items()
    if name not in _CONDITIONS:
        return [f"{where}: unknown condition {name!r}"]
    _, required, optional = _CONDITIONS[name]
    if not isinstance(params, dict):
        return [f"{where}.{name}: params must be a mapping"]
    errors = [f"{where}.{name}: missing {k!r}" for k in sorted(required - params.keys())]
    errors += [f"{where}.{name}: unknown param {k!r}" for k in sorted(params.keys() - required - optional)]
    if "element" in params and params["element"] not in ELEMENTS:
        errors.append(f"{where}.{name}: unknown element {params['element']!r}")
    if "min" in params and not isinstance(params["min"], int):
        errors.append(f"{where}.{name}: 'min' must be an integer")
    return errors


def evaluate_condition(ctx: EffectContext, cond: dict[str, Any]) -> bool:
    (name, params), = cond.items()
    fn, _, _ = _CONDITIONS[name]
    return fn(ctx, params)
