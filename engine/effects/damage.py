"""Damage and healing effects."""

from __future__ import annotations

from typing import Any

from engine.combat import damage_unit, heal_unit
from engine.context import EffectContext
from engine.effects.registry import effect
from engine.prompts import Prompt
from engine.targeting import find_targets
from engine.values import resolve_value


def _has_targets(state: Any, seat: int, p: dict[str, Any]) -> bool:
    return bool(find_targets(state, seat, p["target"]))


@effect("deal_damage", required=("amount", "target"), optional=("split", "if_killed", "different"), can_apply=_has_targets)
def deal_damage(ctx: EffectContext, p: dict[str, Any]) -> None:
    """`different: true` excludes units this card already damaged (e.g. "to 2 different units")."""
    amount = resolve_value(ctx, p["amount"])
    if amount <= 0:
        return
    targets = find_targets(ctx.state, ctx.seat, p["target"])
    if p.get("different"):
        targets = [(t, u) for t, u in targets if u.uid not in ctx.targeted]
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
            allow_skip=not p.get("_required"),
        )
    )
    if uid is not None:
        kills_before = ctx.kills
        ctx.targeted.append(uid)
        damage_unit(ctx, uid, amount)
        if ctx.kills > kills_before and p.get("if_killed"):
            from engine.resolver import resolve_effects  # local import: resolver imports this package

            resolve_effects(ctx, p["if_killed"])


@effect("heal", required=("amount", "target"), optional=("max_hp",), can_apply=_has_targets)
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


@effect("deal_damage_tier", required=("amount",), optional=("tiers", "status", "spare_allies"))
def deal_damage_tier(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Deal the damage to every unit (any owner) on one chosen tier. Optional `status` token for each of them
    first (e.g. stun), `spare_allies` skips your own units."""
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
        if unit_tier != tier or (p.get("spare_allies") and unit.owner == ctx.seat):
            continue
        if p.get("status"):
            unit.status[p["status"]] += 1
            ctx.emit("log.status_added", card=unit.def_id, owner=unit.owner, status=p["status"], count=1)
        damage_unit(ctx, unit.uid, amount)


@effect("heal_all", required=("amount", "target"))
def heal_all(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Give HP to every matching unit."""
    amount = resolve_value(ctx, p["amount"])
    for _, unit in find_targets(ctx.state, ctx.seat, p["target"]):
        heal_unit(ctx, unit.uid, amount)


@effect("deal_damage_each_opponent", required=("amount",), optional=("tiers",))
def deal_damage_each_opponent(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Deal the damage to one chosen unit of each other player (optionally on `tiers`)."""
    amount = resolve_value(ctx, p["amount"])
    if amount <= 0:
        return
    tiers = p.get("tiers", [1, 2, 3, 4])
    for player in ctx.state.players:
        if player.seat == ctx.seat:
            continue
        targets = [(t, u) for t, u in ctx.state.units_of(player.seat) if t in tiers]
        if not targets:
            continue
        uid = ctx.ask(
            Prompt(
                kind="choose_unit",
                key="prompt.deal_damage_opponent",
                params={"amount": amount, "player_seat": player.seat, "skip_key": "ui.prompt.skip_damage"},
                options=tuple(u.uid for _, u in targets),
                allow_skip=True,
            )
        )
        if uid is not None:
            damage_unit(ctx, uid, amount)
