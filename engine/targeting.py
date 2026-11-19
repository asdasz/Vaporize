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
    if tiers in ("with_ally_units", "with_ally_units_or_above"):
        return errors
    if not isinstance(tiers, list) or not tiers or any(t not in (1, 2, 3, 4) for t in tiers):
        errors.append(f"{where}: tiers must be a non-empty list of 1-4, with_ally_units or with_ally_units_or_above")
    return errors


def find_targets(state: GameState, seat: int, spec: dict[str, Any]) -> list[tuple[int, CardInstance]]:
    """All units matching the selector as (tier, unit), in seat order. Allies and enemies alike unless restricted."""
    side = spec.get("side", "any")
    raw_tiers = spec.get("tiers", [1, 2, 3, 4])
    if raw_tiers == "with_ally_units":  # tiers where you have at least one unit
        tiers = {tier for tier, _ in state.units_of(seat)}
    elif raw_tiers == "with_ally_units_or_above":  # 111: "the same tier as any of your units or 1 tier above it"
        tiers = {t for tier, _ in state.units_of(seat) for t in (tier, tier + 1) if t <= 4}
    else:
        tiers = set(raw_tiers)
    found: list[tuple[int, CardInstance]] = []
    for player in state.players:
        if side == "ally" and player.seat != seat:
            continue
        if side == "enemy" and player.seat == seat:
            continue
        units = [(tier, unit) for tier, unit in state.units_of(player.seat) if tier in tiers]
        if player.seat != seat:
            units = apply_taunt(units)
        found += units
    return found


def apply_taunt(units: list[tuple[int, CardInstance]]) -> list[tuple[int, CardInstance]]:
    """Enemy units can't target another of a player's units if they could target one with `taunt` instead."""
    taunting = [(t, u) for t, u in units if u.taunt]
    return taunting or units
