"""Resolves effect lists (with if/then/else) against the registry."""

from __future__ import annotations

from typing import Any

import engine.effects  # noqa: F401  (registers primitives)
from engine.conditions import evaluate_condition
from engine.context import EffectContext
from engine.effects.registry import COMMON_KEYS, get_effect


def resolve_effects(ctx: EffectContext, nodes: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> None:
    for node in nodes:
        if "if" in node:
            branch = node.get("then", []) if evaluate_condition(ctx, node["if"]) else node.get("else", [])
            resolve_effects(ctx, branch)
            continue
        spec = get_effect(node["do"])
        params = {k: v for k, v in node.items() if k not in COMMON_KEYS}
        spec.fn(ctx, params)
