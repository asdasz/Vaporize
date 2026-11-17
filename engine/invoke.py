"""Invoke: each class turns something into a value (Mage: spend any amount of mana)."""

from __future__ import annotations

from engine.context import EffectContext
from engine.prompts import Prompt

INVOKE_MODES = ("spend_resource_any",)


def invoke_bonus(ctx: EffectContext) -> int:
    """Everything added to this card's invoke value.

    - one-off bonuses for this card (e.g. "the next spell you play gets +1"),
    - for spells: the class passive (Mage +1) and units on your board with `spell_invoke_bonus`.
    """
    bonus = ctx.invoke_extra
    if ctx.source is None or ctx.catalog.card(ctx.source.def_id).type != "spell":
        return bonus
    bonus += sum(int(p.get("amount", 0)) for p in ctx.class_def.passives if p.get("modifier") == "spell_invoke_bonus")
    for _, unit in ctx.state.units_of(ctx.seat):
        for mod in ctx.catalog.card(unit.def_id).modifiers:
            bonus += int(mod.get("spell_invoke_bonus", 0))
    return bonus


def invoke(ctx: EffectContext) -> int:
    """Invoke once per card resolution; later uses on the same card reuse the value."""
    if ctx.invoke_value is not None:
        return ctx.invoke_value
    cdef = ctx.class_def
    mode = cdef.invoke.get("mode")
    bonus = invoke_bonus(ctx)
    if mode == "spend_resource_any":
        spent = ctx.ask(
            Prompt(
                kind="number",
                key="prompt.invoke",
                params={"resource": cdef.resource.key, "bonus": bonus},
                min=0,
                max=ctx.player.resource,
            )
        )
        ctx.player.resource -= spent
    else:
        raise ValueError(f"unknown invoke mode {mode!r} for class {cdef.id}")
    value = spent + bonus
    ctx.invoke_value = value
    ctx.emit("log.invoke", seat=ctx.seat, spent=spent, value=value, resource=cdef.resource.key)
    return value
