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
VALUE_PARAMS = frozenset({"amount", "count"})
# Params that must be plain non-negative integers.
INT_PARAMS = frozenset({"max_hp", "draw"})


@dataclass(frozen=True)
class EffectSpec:
    name: str
    fn: EffectFn
    required: frozenset[str]
    optional: frozenset[str]


_REGISTRY: dict[str, EffectSpec] = {}


def effect(
    name: str, *, required: tuple[str, ...] = (), optional: tuple[str, ...] = ()
) -> Callable[[EffectFn], EffectFn]:
    def decorator(fn: EffectFn) -> EffectFn:
        if name in _REGISTRY:
            raise ValueError(f"effect {name!r} registered twice")
        _REGISTRY[name] = EffectSpec(name, fn, frozenset(required), frozenset(optional))
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
        if "if" in node:
            errors += validate_condition(node["if"], f"{w}.if")
            errors += validate_effects(node.get("then", []), f"{w}.then")
            errors += validate_effects(node.get("else", []), f"{w}.else")
            extra = node.keys() - {"if", "then", "else"}
            errors += [f"{w}: unknown key {k!r} in if-block" for k in sorted(extra)]
            continue
        name = node.get("do")
        if name not in _REGISTRY:
            errors.append(f"{w}: unknown effect {name!r}")
            continue
        spec = _REGISTRY[name]
        params = node.keys() - COMMON_KEYS
        errors += [f"{w} ({name}): missing {k!r}" for k in sorted(spec.required - params)]
        errors += [
            f"{w} ({name}): unknown param {k!r}"
            for k in sorted(params - spec.required - spec.optional)
        ]
        errors += _validate_params(node, f"{w} ({name})")
    return errors


def _validate_params(node: dict[str, Any], where: str) -> list[str]:
    from engine.rules import KEYWORDS
    from engine.targeting import validate_target
    from engine.values import validate_value

    errors: list[str] = []
    for key in VALUE_PARAMS & node.keys():
        errors += validate_value(node[key], f"{where}.{key}")
    for key in INT_PARAMS & node.keys():
        if isinstance(node[key], bool) or not isinstance(node[key], int) or node[key] < 0:
            errors.append(f"{where}: {key!r} must be a non-negative integer")
    if "target" in node:
        errors += validate_target(node["target"], f"{where}.target")
    if "keyword" in node and node["keyword"] not in KEYWORDS:
        errors.append(f"{where}: unknown keyword {node['keyword']!r}")
    if "scope" in node and node["scope"] not in ("same_tier",):
        errors.append(f"{where}: unknown scope {node['scope']!r}")
    if "required" in node and not isinstance(node["required"], bool):
        errors.append(f"{where}: 'required' must be true or false")
    return errors
