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


def _value_at_least(ctx: EffectContext, p: dict[str, Any]) -> bool:
    from engine.values import resolve_value  # local import: values -> invoke -> context

    return resolve_value(ctx, p["value"]) >= p["min"]


def _ally_tiers_at_least(ctx: EffectContext, p: dict[str, Any]) -> bool:
    """Your units occupy at least `min` different tiers ("rows")."""
    return len({tier for tier, _ in ctx.state.units_of(ctx.seat)}) >= p["min"]


def _unique_played_elements_at_least(ctx: EffectContext, p: dict[str, Any]) -> bool:
    source_uid = ctx.source.uid if ctx.source else None
    played = [x for x in ctx.player.played_this_turn if not (p.get("other") and x.uid == source_uid)]
    return len({e for x in played for e in x.elements}) >= p["min"]


def _matches(elements: tuple[str, ...], filt: str, primary: tuple[str, ...]) -> bool:
    if filt == "non_primary":
        return any(e not in primary for e in elements)
    return False


def _played_matching(ctx: EffectContext, p: dict[str, Any]) -> bool:
    """At least `min` cards matching the filter were played this turn."""
    primary = ctx.class_def.primary_elements
    return sum(1 for x in ctx.player.played_this_turn if _matches(x.elements, p["filter"], primary)) >= p["min"]


# name -> (function, required params, optional params)
_CONDITIONS: dict[str, tuple[ConditionFn, frozenset[str], frozenset[str]]] = {
    "played_this_turn": (_played_this_turn, frozenset({"element", "min"}), frozenset({"other"})),
    "in_discard": (_in_discard, frozenset({"element", "min"}), frozenset()),
    "value_at_least": (_value_at_least, frozenset({"value", "min"}), frozenset()),
    "ally_tiers_at_least": (_ally_tiers_at_least, frozenset({"min"}), frozenset()),
    "unique_played_elements_at_least": (_unique_played_elements_at_least, frozenset({"min"}), frozenset({"other"})),
    "played_matching": (_played_matching, frozenset({"filter", "min"}), frozenset()),
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
    if "filter" in params and params["filter"] not in ("non_primary",):
        errors.append(f"{where}.{name}: unknown filter {params['filter']!r}")
    if "value" in params:
        from engine.values import validate_value

        errors += validate_value(params["value"], f"{where}.{name}.value")
    return errors


def evaluate_condition(ctx: EffectContext, cond: dict[str, Any]) -> bool:
    (name, params), = cond.items()
    fn, _, _ = _CONDITIONS[name]
    return fn(ctx, params)
