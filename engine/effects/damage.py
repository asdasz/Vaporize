"""Damage and healing effects."""

from __future__ import annotations

from typing import Any

from engine.combat import damage_unit, heal_unit
from engine.context import EffectContext
from engine.effects.registry import effect
from engine.prompts import Prompt
from engine.targeting import find_targets
from engine.values import resolve_value


@effect("deal_damage", required=("amount", "target"), optional=("split",))
def deal_damage(ctx: EffectContext, p: dict[str, Any]) -> None:
    amount = resolve_value(ctx, p["amount"])
    if amount <= 0:
        return
    targets = find_targets(ctx.state, ctx.seat, p["target"])
    if not targets:
        return
    split = ctx.keywords.get("split") or ({"scope": None} if p.get("split") else None)
    if split is not None:
        tiers = {unit.uid: tier for tier, unit in targets}
        answer = ctx.ask(
            Prompt(
                kind="split_damage",
                key="prompt.split_damage",
                params={"amount": amount, "skip_key": "ui.prompt.skip_damage"},
                options=tuple(tiers),
                total=amount,
                same_tier=split.get("scope") == "same_tier",
                tiers=tiers,
                allow_skip=True,
            )
        )
        for uid, part in (answer or {}).items():
            damage_unit(ctx, uid, part)
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.deal_damage",
            params={"amount": amount, "skip_key": "ui.prompt.skip_damage"},
            options=tuple(unit.uid for _, unit in targets),
            allow_skip=True,
        )
    )
    if uid is not None:
        damage_unit(ctx, uid, amount)


@effect("heal", required=("amount", "target"), optional=("max_hp",))
def heal(ctx: EffectContext, p: dict[str, Any]) -> None:
    amount = resolve_value(ctx, p["amount"])
    if amount <= 0:
        return
    targets = find_targets(ctx.state, ctx.seat, p["target"])
    if not targets:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.heal",
            params={"amount": amount, "max_hp": p.get("max_hp"), "skip_key": "ui.prompt.skip_heal"},
            options=tuple(unit.uid for _, unit in targets),
            allow_skip=True,
        )
    )
    if uid is not None:
        heal_unit(ctx, uid, amount, p.get("max_hp"))


@effect("deal_damage_tier", required=("amount",), optional=("tiers",))
def deal_damage_tier(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Deal the damage to every unit (any owner) on one chosen tier."""
    allowed = p.get("tiers", [1, 2, 3, 4])
    units = find_targets(ctx.state, ctx.seat, {"side": "any", "tiers": allowed})
    tiers = sorted({tier for tier, _ in units})
    if not tiers:
        return
    amount = resolve_value(ctx, p["amount"])
    if amount <= 0:
        return
    tier = ctx.ask(
        Prompt(
            kind="choose_tier",
            key="prompt.deal_damage_tier",
            params={"amount": amount, "skip_key": "ui.prompt.skip_damage"},
            options=tuple(tiers),
            allow_skip=True,
        )
    )
    if tier is None:
        return
    for unit_tier, unit in units:
        if unit_tier == tier:
            damage_unit(ctx, unit.uid, amount)
