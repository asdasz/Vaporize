"""Moving units between tiers: develop, degrade."""

from __future__ import annotations

from typing import Any

from engine.cards import CardInstance
from engine.context import EffectContext
from engine.development import MAX_TIER, check_develop, develop_unit
from engine.effects.registry import effect
from engine.errors import IllegalAction
from engine.prompts import Prompt
from engine.state import GameState
from engine.targeting import find_targets
from engine.zones import SlotRow


def _row(state: GameState, owner: int, tier: int) -> SlotRow:
    return state.tier4 if tier == MAX_TIER else state.players[owner].tiers[tier]


def can_degrade(state: GameState, tier: int, unit: CardInstance) -> bool:
    """Not from tier 1 (or as an undeveloped token), and only if the tier below has a free spot."""
    if tier <= 1 or state.players[unit.owner].tokens.find(unit.uid):
        return False
    return _row(state, unit.owner, tier - 1).has_free()


def degrade_unit(ctx: EffectContext, tier: int, unit: CardInstance) -> None:
    """Move a unit down one tier. From tier 4 it goes to its owner's tier 3."""
    _row(ctx.state, unit.owner, tier).take(unit.uid)
    _row(ctx.state, unit.owner, tier - 1).place(unit)
    ctx.emit("log.unit_degraded", card=unit.def_id, owner=unit.owner, tier=tier - 1)


@effect("degrade", required=("target",), optional=("refund", "per_opponent", "times"))
def degrade(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Degrade a chosen unit (`times` times, choosing again each time; the same unit may be picked again).
    With `refund`, gain the inf its current tier cost to develop into.
    With `per_opponent`, degrade one unit of each other player instead."""
    from engine.values import resolve_value  # local import: values -> invoke -> context

    if p.get("per_opponent"):
        for player in ctx.state.players:
            if player.seat != ctx.seat:
                _degrade_one(ctx, [(t, u) for t, u in ctx.state.units_of(player.seat) if can_degrade(ctx.state, t, u)], False)
        return
    for _ in range(resolve_value(ctx, p.get("times", 1))):
        options = [(t, u) for t, u in find_targets(ctx.state, ctx.seat, p["target"]) if can_degrade(ctx.state, t, u)]
        if not options:
            return
        _degrade_one(ctx, options, bool(p.get("refund")))


def _degrade_one(ctx: EffectContext, options: list[tuple[int, CardInstance]], refund: bool) -> None:
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.degrade",
            params={"skip_key": "ui.prompt.skip_degrade", "refund": refund},
            options=tuple(u.uid for _, u in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    tier, unit = next((t, u) for t, u in options if u.uid == uid)
    degrade_unit(ctx, tier, unit)
    if refund:
        owner_class = ctx.catalog.cls(ctx.state.players[unit.owner].class_id)
        amount = owner_class.tiers[tier].develop_cost or 0
        ctx.player.inf += amount
        ctx.emit("log.gain_inf", seat=ctx.seat, amount=amount)


@effect("develop", optional=("cost_override",))
def develop(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Develop one of your units (for `cost_override` inf, e.g. 0 = free)."""
    cost = p.get("cost_override")
    options = []
    for _, unit in ctx.state.units_of(ctx.seat):
        try:
            options.append(check_develop(ctx.state, ctx.catalog, ctx.seat, unit.uid, cost))
        except IllegalAction:
            continue
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.develop",
            params={"cost": cost, "skip_key": "ui.prompt.skip_develop"},
            options=tuple(o.uid for o in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    develop_unit(ctx.state, ctx.catalog, ctx.seat, next(o for o in options if o.uid == uid), ctx.events)


def _slot_of(state: GameState, unit: CardInstance) -> tuple[SlotRow, int]:
    owner = state.players[unit.owner]
    for row in (*owner.tiers.values(), state.tier4):
        for i, c in enumerate(row.slots):
            if c is not None and c.uid == unit.uid:
                return row, i
    raise KeyError(unit.uid)


@effect("swap_units", optional=("heal", "damage", "per_opponent"))
def swap_units(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Swap the places of 2 of your units (tokens that haven't developed can't be swapped), then give them
    `heal` HP. With `per_opponent`, do it for every other player too, dealing `damage` to theirs instead."""
    from engine.combat import damage_unit, heal_unit

    seats = [ctx.seat] + ([pl.seat for pl in ctx.state.players if pl.seat != ctx.seat] if p.get("per_opponent") else [])
    for seat in seats:
        units = [u for _, u in ctx.state.units_of(seat) if not ctx.state.players[seat].tokens.find(u.uid)]
        if len(units) < 2:
            continue
        chosen = ctx.ask(
            Prompt(
                kind="choose_cards",
                key="prompt.swap_units",
                params={"player_seat": seat, "skip_key": "ui.prompt.skip_swap"},
                options=tuple({"uid": u.uid, "unit": True} for u in units),
                min=2,
                max=2,
                allow_skip=True,
            )
        )
        if not chosen:
            continue
        a, b = (find_unit_by(ctx.state, uid) for uid in chosen)
        (row_a, i_a), (row_b, i_b) = _slot_of(ctx.state, a), _slot_of(ctx.state, b)
        row_a.slots[i_a], row_b.slots[i_b] = b, a
        ctx.emit("log.units_swapped", seat=ctx.seat, owner=seat, a=a.def_id, b=b.def_id)
        for unit in (a, b):
            if seat == ctx.seat and p.get("heal"):
                heal_unit(ctx, unit.uid, p["heal"])
            elif seat != ctx.seat and p.get("damage"):
                damage_unit(ctx, unit.uid, p["damage"])


def find_unit_by(state: GameState, uid: str) -> CardInstance:
    from engine.combat import find_unit

    unit = find_unit(state, uid)
    assert unit is not None
    return unit
