"""Target selectors: which units an effect may choose from."""

from __future__ import annotations

from typing import Any

from engine.cards import CardInstance
from engine.state import GameState

SIDES = ("any", "ally", "enemy")


def validate_target(spec: Any, where: str) -> list[str]:
    if not isinstance(spec, dict):
        return [f"{where}: target must be a mapping like {{side: any, tiers: [1, 2, 3]}}"]
    errors = [f"{where}: unknown target key {k!r}" for k in sorted(spec.keys() - {"side", "tiers"})]
    if spec.get("side", "any") not in SIDES:
        errors.append(f"{where}: side must be one of {SIDES}")
    tiers = spec.get("tiers", [1, 2, 3, 4])
    if tiers == "with_ally_units":
        return errors
    if not isinstance(tiers, list) or not tiers or any(t not in (1, 2, 3, 4) for t in tiers):
        errors.append(f"{where}: tiers must be a non-empty list of 1-4, or with_ally_units")
    return errors


def find_targets(state: GameState, seat: int, spec: dict[str, Any]) -> list[tuple[int, CardInstance]]:
    """All units matching the selector as (tier, unit), in seat order. Allies and enemies alike unless restricted."""
    side = spec.get("side", "any")
    raw_tiers = spec.get("tiers", [1, 2, 3, 4])
    if raw_tiers == "with_ally_units":  # tiers where you have at least one unit
        tiers = {tier for tier, _ in state.units_of(seat)}
    else:
        tiers = set(raw_tiers)
    found: list[tuple[int, CardInstance]] = []
    for player in state.players:
        if side == "ally" and player.seat != seat:
            continue
        if side == "enemy" and player.seat == seat:
            continue
        found += [(tier, unit) for tier, unit in state.units_of(player.seat) if tier in tiers]
    return found
