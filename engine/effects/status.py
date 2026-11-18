"""Status tokens: shield, stun, freeze."""

from __future__ import annotations

from typing import Any

from engine.combat import find_unit
from engine.context import EffectContext
from engine.effects.registry import effect
from engine.prompts import Prompt
from engine.targeting import find_targets
from engine.values import resolve_value


def _add_status(ctx: EffectContext, status: str, p: dict[str, Any]) -> None:
    count = resolve_value(ctx, p.get("count", 1))
    targets = find_targets(ctx.state, ctx.seat, p["target"])
    if count <= 0 or not targets:
        return
    uid = ctx.ask(
        Prompt(
            kind="choose_unit",
            key=f"prompt.{status}",
            params={"count": count, "skip_key": "ui.prompt.skip_status"},
            options=tuple(unit.uid for _, unit in targets),
            allow_skip=not p.get("_required"),
        )
    )
    unit = find_unit(ctx.state, uid) if uid is not None else None
    if unit is None:
        return
    unit.status[status] += count
    ctx.emit("log.status_added", card=unit.def_id, owner=unit.owner, status=status, count=count)


@effect("shield", required=("target",), optional=("count",))
def shield(ctx: EffectContext, p: dict[str, Any]) -> None:
    _add_status(ctx, "shield", p)


@effect("stun", required=("target",), optional=("count",))
def stun(ctx: EffectContext, p: dict[str, Any]) -> None:
    _add_status(ctx, "stun", p)


@effect("freeze", required=("target",), optional=("count",))
def freeze(ctx: EffectContext, p: dict[str, Any]) -> None:
    _add_status(ctx, "freeze", p)
