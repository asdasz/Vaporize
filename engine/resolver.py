"""Resolves effect lists (with if/then/else) against the registry."""

from __future__ import annotations

import json
from typing import Any

import engine.effects  # noqa: F401  (registers primitives)
from engine.conditions import evaluate_condition
from engine.context import EffectContext
from engine.effects.registry import COMMON_KEYS, get_effect
from engine.prompts import Prompt


def resolve_effects(ctx: EffectContext, nodes: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> None:
    for node in nodes:
        if "if" in node:
            if node.get("once_per_turn"):
                # Check after every trigger; once it has fired, skip it for the rest of the turn.
                key = f"{ctx.source.uid if ctx.source else '-'}:{json.dumps(node['if'], sort_keys=True)}"
                if key in ctx.player.turn_flags or not evaluate_condition(ctx, node["if"]):
                    continue
                ctx.player.turn_flags.append(key)
                resolve_effects(ctx, node.get("then", []))
                continue
            branch = node.get("then", []) if evaluate_condition(ctx, node["if"]) else node.get("else", [])
            resolve_effects(ctx, branch)
            continue
        if "choose_one" in node:
            options = node["choose_one"]
            card_id = ctx.source.def_id if ctx.source else None
            index = ctx.ask(
                Prompt(
                    kind="choose_option",
                    key="prompt.choose_one",
                    params={"card": card_id, "label": node.get("label")},  # label: which option texts (several per card)
                    options=tuple(range(len(options))),
                )
            )
            resolve_effects(ctx, options[index])
            continue
        spec = get_effect(node["do"])
        params = {k: v for k, v in node.items() if k not in COMMON_KEYS}
        if node.get("required"):
            params["_required"] = True  # mandatory (negative) part of the card: it can't be skipped
        spec.fn(ctx, params)
