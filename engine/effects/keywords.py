"""Keywords granted to the card that is resolving (e.g. Split)."""

from __future__ import annotations

from typing import Any

from engine.context import EffectContext
from engine.effects.registry import effect


@effect("grant_keyword", required=("keyword",), optional=("scope",))
def grant_keyword(ctx: EffectContext, p: dict[str, Any]) -> None:
    ctx.keywords[p["keyword"]] = {"scope": p.get("scope")}
    ctx.emit("log.keyword_gained", seat=ctx.seat, keyword=p["keyword"])
