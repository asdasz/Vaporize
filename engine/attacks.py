"""Unit attacks (rulebook: Attacking)."""

from __future__ import annotations

from engine.cards import CardInstance
from engine.cardview import attacks_allowed
from engine.catalog import Catalog
from engine.combat import damage_unit, find_unit
from engine.context import EffectContext
from engine.errors import IllegalAction
from engine.events import Event
from engine.resolver import resolve_effects
from engine.state import GameState


def _tier_of(state: GameState, uid: str) -> tuple[int, int, CardInstance] | None:
    """(owner seat, tier, unit) for any unit on the board."""
    for player in state.players:
        for tier, unit in state.units_of(player.seat):
            if unit.uid == uid:
                return player.seat, tier, unit
    return None


def check_attack(state: GameState, seat: int, attacker_uid: str, target_uid: str | None = None) -> None:
    found = _tier_of(state, attacker_uid)
    if found is None or found[0] != seat:
        raise IllegalAction("error.not_your_unit")
    _, tier, unit = found
    if unit.tapped:
        raise IllegalAction("error.unit_tapped")
    if unit.status["stun"] > 0:
        raise IllegalAction("error.unit_stunned")
    if unit.attack_value <= 0:
        raise IllegalAction("error.no_attack")
    if target_uid is None:
        return
    target = _tier_of(state, target_uid)
    if target is None or target[0] == seat:
        raise IllegalAction("error.invalid_target")
    if target[1] not in (tier, tier + 1):
        raise IllegalAction("error.out_of_range")


def attack_targets(state: GameState, seat: int, attacker_uid: str) -> list[str]:
    """Enemy units the attacker can reach: same tier or one tier higher."""
    try:
        check_attack(state, seat, attacker_uid)
    except IllegalAction:
        return []
    found = _tier_of(state, attacker_uid)
    assert found is not None
    tier = found[1]
    return [
        unit.uid
        for player in state.players
        if player.seat != seat
        for t, unit in state.units_of(player.seat)
        if t in (tier, tier + 1)
    ]


def legal_attacks(state: GameState, seat: int) -> dict[str, list[str]]:
    result = {}
    for _, unit in state.units_of(seat):
        targets = attack_targets(state, seat, unit.uid)
        if targets:
            result[unit.uid] = targets
    return result


def attack(state: GameState, catalog: Catalog, seat: int, attacker_uid: str, target_uid: str, events: list[Event]) -> None:
    check_attack(state, seat, attacker_uid, target_uid)
    attacker = find_unit(state, attacker_uid)
    target = find_unit(state, target_uid)
    assert attacker is not None and target is not None
    ctx = EffectContext(state, catalog, seat, attacker, events)
    events.append(
        Event("log.attack", {"seat": seat, "attacker": attacker.def_id, "target": target.def_id, "owner": target.owner})
    )
    attacker.attacks_made += 1
    attacker.tapped = attacker.attacks_made >= attacks_allowed(attacker, catalog)  # tapped when out of attacks
    damage_unit(ctx, target_uid, attacker.attack_value)
    if ctx.kills:
        player = state.players[seat]
        vp = sum(m["amount"] for m in player.turn_modifiers if m["kind"] == "vp_per_attack_kill")
        if vp:
            player.vp += vp
            events.append(Event("log.gain_vp", {"seat": seat, "amount": vp}))
        nodes = catalog.card(attacker.def_id).triggers.get("on_kill", ())
        if nodes:
            resolve_effects(ctx, nodes)
