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


@effect("degrade", required=("target",), optional=("refund",))
def degrade(ctx: EffectContext, p: dict[str, Any]) -> None:
    """Degrade a chosen unit. With `refund`, gain the inf its current tier cost to develop into."""
    options = [(t, u) for t, u in find_targets(ctx.state, ctx.seat, p["target"]) if can_degrade(ctx.state, t, u)]
    if not options:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key="prompt.degrade",
            params={"skip_key": "ui.prompt.skip_degrade", "refund": bool(p.get("refund"))},
            options=tuple(u.uid for _, u in options),
            allow_skip=True,
        )
    )
    if uid is None:
        return
    tier, unit = next((t, u) for t, u in options if u.uid == uid)
    degrade_unit(ctx, tier, unit)
    if p.get("refund"):
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
