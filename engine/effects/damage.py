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


@effect("deal_damage_tier", required=("amount",), optional=("tiers", "status", "spare_allies", "exclude_self"))
def deal_damage_tier(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Deal the damage to every unit (any owner) on one chosen tier. Optional `status` token for each of them
    first (e.g. stun), `spare_allies` skips your own units."""
    if p.get("tiers") == "source":  # the tier this unit is on (e.g. "the tier it enters"), no choice
        from engine.development import unit_tier

        found = unit_tier(ctx.state, ctx.seat, ctx.source.uid) if ctx.source else None
        if found is None:
            return
        units = [(t, u) for t, u in find_targets(ctx.state, ctx.seat, {"side": "any"}) if t == found[0]]
        amount = resolve_value(ctx, p["amount"])
        for _, unit in units:
            if not (p.get("exclude_self") and unit.uid == ctx.source.uid):
                damage_unit(ctx, unit.uid, amount)
        return
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


@effect("deal_damage_all", required=("amount",), optional=("spare_allies",))
def deal_damage_all(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Deal the damage to every unit in the game (optionally not yours)."""
    amount = resolve_value(ctx, p["amount"])
    for _, unit in find_targets(ctx.state, ctx.seat, {"side": "any"}):
        if not (p.get("spare_allies") and unit.owner == ctx.seat):
            damage_unit(ctx, unit.uid, amount)


@effect("status_damaged", required=("status",))
def status_damaged(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Put a status token on every unit this card has harmed (lost HP), if it's still alive."""
    from engine.combat import find_unit

    for uid in dict.fromkeys(ctx.damaged):
        unit = find_unit(ctx.state, uid)
        if unit is not None:
            unit.status[p["status"]] += 1
            ctx.emit("log.status_added", card=unit.def_id, owner=unit.owner, status=p["status"], count=1)


def _destroy_options(ctx: EffectContext, seat: int, max_cost: int | None) -> list[str]:
    return [
        u.uid
        for _, u in ctx.state.units_of(seat)
        if max_cost is None or u.is_token or ctx.catalog.card(u.def_id).cost <= max_cost
    ]


@effect("destroy_each_opponent", optional=("max_cost",))
def destroy_each_opponent(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Kill one chosen unit of each other player (printed cost <= `max_cost`). Shields don't stop it."""
    from engine.combat import destroy_unit, find_unit

    for player in ctx.state.players:
        if player.seat == ctx.seat:
            continue
        options = _destroy_options(ctx, player.seat, p.get("max_cost"))
        if not options:
            continue
        uid = ctx.ask(
            Prompt(
                kind="choose_unit",
                key="prompt.destroy",
                params={"player_seat": player.seat, "max_cost": p.get("max_cost"), "skip_key": "ui.prompt.skip_kill"},
                options=tuple(options),
                allow_skip=True,
            )
        )
        unit = find_unit(ctx.state, uid) if uid else None
        if unit is not None:
            destroy_unit(ctx, unit)


@effect("destroy_tier")
def destroy_tier(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Kill every unit on a chosen tier (yours too)."""
    from engine.combat import destroy_unit

    units = find_targets(ctx.state, ctx.seat, {"side": "any"})
    tiers = sorted({t for t, _ in units})
    if not tiers:
        return
    tier = ctx.ask(
        Prompt(kind="choose_tier", key="prompt.destroy_tier", params={"skip_key": "ui.prompt.skip_kill"}, options=tuple(tiers), allow_skip=True)
    )
    if tier is None:
        return
    for t, unit in units:
        if t == tier:
            destroy_unit(ctx, unit)


@effect("sacrifice_ally", optional=("transfer_hp", "vp"))
def sacrifice_ally(ctx: EffectContext, p: dict[str, Any]) -> None:
    """You may kill another of your units. `transfer_hp`: this unit gains its HP. `vp: tier_minus_one`: gain VP
    equal to the killed unit's tier − 1."""
    from engine.combat import destroy_unit

    source_uid = ctx.source.uid if ctx.source else None
    options = [(t, u) for t, u in ctx.state.units_of(ctx.seat) if u.uid != source_uid]
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.sacrifice",
            params={"skip_key": "ui.prompt.skip_sacrifice"},
            options=tuple(u.uid for _, u in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    tier, unit = next((t, u) for t, u in options if u.uid == uid)
    hp = unit.current_hp or 0
    destroy_unit(ctx, unit)
    if p.get("transfer_hp") and ctx.source is not None:
        ctx.source.current_hp = (ctx.source.current_hp or 0) + hp
        ctx.emit("log.heal", card=ctx.source.def_id, owner=ctx.source.owner, amount=hp)
    if p.get("vp") == "tier_minus_one" and tier > 1:
        ctx.player.vp += tier - 1
        ctx.emit("log.gain_vp", seat=ctx.seat, amount=tier - 1)


@effect("heal_self", required=("amount",))
def heal_self(ctx: EffectContext, p: dict[str, Any]) -> None:
    """The unit with this ability gains HP (no cap)."""
    if ctx.source is not None:
        heal_unit(ctx, ctx.source.uid, resolve_value(ctx, p["amount"]))
