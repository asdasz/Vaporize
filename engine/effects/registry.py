"""Effect registry. Every card effect is a named primitive registered here once."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from engine.conditions import validate_condition
from engine.context import EffectContext

EffectFn = Callable[[EffectContext, dict[str, Any]], None]

# Keys allowed on every effect node in addition to the effect's own params.
COMMON_KEYS = frozenset({"do", "required"})
# Params that hold a value expression (int or {invoke: N}).
VALUE_PARAMS = frozenset({"amount", "count", "times"})
# Params that must be plain non-negative integers.
INT_PARAMS = frozenset({"max_hp", "draw", "vp_per_kill", "element_amount", "cost_override", "heal", "damage", "attack", "extra_attacks", "up_to"})
BOOL_PARAMS = frozenset({"exceed_limit", "split", "up_to_limit", "refund", "discard_any", "different", "spare_allies", "per_opponent", "rest_choice", "all"})


# For effects marked `required: true`: can this effect happen at all right now? (state, seat, params)
CanApplyFn = Callable[[Any, int, dict[str, Any]], bool]


@dataclass(frozen=True)
class EffectSpec:
    name: str
    fn: EffectFn
    required: frozenset[str]
    optional: frozenset[str]
    can_apply: CanApplyFn | None = None


_REGISTRY: dict[str, EffectSpec] = {}


def effect(
    name: str,
    *,
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    can_apply: CanApplyFn | None = None,
) -> Callable[[EffectFn], EffectFn]:
    def decorator(fn: EffectFn) -> EffectFn:
        if name in _REGISTRY:
            raise ValueError(f"effect {name!r} registered twice")
        _REGISTRY[name] = EffectSpec(name, fn, frozenset(required), frozenset(optional), can_apply)
        return fn

    return decorator


def get_effect(name: str) -> EffectSpec:
    return _REGISTRY[name]


def registered_effects() -> list[str]:
    return sorted(_REGISTRY)


def validate_effects(nodes: Any, where: str) -> list[str]:
    """Validate a list of effect nodes (recursively for if/then/else)."""
    if not isinstance(nodes, list):
        return [f"{where}: effects must be a list"]
    errors: list[str] = []
    for i, node in enumerate(nodes):
        w = f"{where}[{i}]"
        if not isinstance(node, dict):
            errors.append(f"{w}: effect must be a mapping")
            continue
        if "choose_one" in node:
            extra = node.keys() - {"choose_one", "label"}
            errors += [f"{w}: unknown key {k!r} in choose_one" for k in sorted(extra)]
            options = node["choose_one"]
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{w}: choose_one needs a list of at least 2 effect lists")
                continue
            for j, option in enumerate(options):
                errors += validate_effects(option, f"{w}.choose_one[{j}]")
            continue
        if "if" in node:
            errors += validate_condition(node["if"], f"{w}.if")
            errors += validate_effects(node.get("then", []), f"{w}.then")
            errors += validate_effects(node.get("else", []), f"{w}.else")
            extra = node.keys() - {"if", "then", "else", "once_per_turn"}
            errors += [f"{w}: unknown key {k!r} in if-block" for k in sorted(extra)]
            if "once_per_turn" in node and not isinstance(node["once_per_turn"], bool):
                errors.append(f"{w}: once_per_turn must be true or false")
            if node.get("once_per_turn") and "else" in node:
                errors.append(f"{w}: once_per_turn can't have an else branch")
            continue
        name = node.get("do")
        if name not in _REGISTRY:
            errors.append(f"{w}: unknown effect {name!r}")
            continue
        spec = _REGISTRY[name]
        if node.get("required") and spec.can_apply is None:
            errors.append(f"{w} ({name}): this effect can't be marked required (no can_apply check)")
        params = node.keys() - COMMON_KEYS
        errors += [f"{w} ({name}): missing {k!r}" for k in sorted(spec.required - params)]
        errors += [
            f"{w} ({name}): unknown param {k!r}"
            for k in sorted(params - spec.required - spec.optional)
        ]
        errors += _validate_params(node, f"{w} ({name})")
    return errors


def _validate_params(node: dict[str, Any], where: str) -> list[str]:
    from engine.rules import CARD_TYPES, ELEMENTS, KEYWORDS
    from engine.targeting import validate_target
    from engine.values import validate_value

    errors: list[str] = []
    for key in ("units",):
        if key in node:
            errors += validate_value(node[key], f"{where}.{key}")
    for key in VALUE_PARAMS & node.keys():
        errors += validate_value(node[key], f"{where}.{key}")
    for key in INT_PARAMS & node.keys():
        if isinstance(node[key], bool) or not isinstance(node[key], int) or node[key] < 0:
            errors.append(f"{where}: {key!r} must be a non-negative integer")
    for key in BOOL_PARAMS & node.keys():
        if not isinstance(node[key], bool):
            errors.append(f"{where}: {key!r} must be true or false")
    if "element" in node and node["element"] not in ELEMENTS:
        errors.append(f"{where}: unknown element {node['element']!r}")
    if "card_type" in node and node["card_type"] not in CARD_TYPES:
        errors.append(f"{where}: unknown card_type {node['card_type']!r}")
    if "tiers" in node and node["tiers"] != "with_ally_units" and node.get("do") != "swap_units" and (
        not isinstance(node["tiers"], list) or any(t not in (1, 2, 3, 4) for t in node["tiers"])
    ):
        errors.append(f"{where}: tiers must be a list of 1-4")
    if "target" in node:
        errors += validate_target(node["target"], f"{where}.target")
    if "keyword" in node and node["keyword"] not in KEYWORDS:
        errors.append(f"{where}: unknown keyword {node['keyword']!r}")
    if "scope" in node and node["scope"] not in ("same_tier",):
        errors.append(f"{where}: unknown scope {node['scope']!r}")
    if "position" in node and node["position"] not in ("top", "bottom"):
        errors.append(f"{where}: position must be top or bottom")
    for key in ("then", "if_killed"):  # nested effect lists
        if key in node and "do" in node:
            errors += validate_effects(node[key], f"{where}.{key}")
    if "market" in node and node["market"] not in ("shared", "private", "all"):
        errors.append(f"{where}: market must be shared, private or all")
    if "status" in node and node["status"] not in ("shield", "stun", "freeze"):
        errors.append(f"{where}: unknown status {node['status']!r}")
    if "required" in node and not isinstance(node["required"], bool):
        errors.append(f"{where}: 'required' must be true or false")
    return errors
