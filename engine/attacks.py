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
from engine.targeting import apply_taunt
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
    if target[1] not in (tier, tier + 1) and not unit.temp_any_tier:
        raise IllegalAction("error.out_of_range")
    if target_uid not in attack_targets(state, seat, attacker_uid):
        raise IllegalAction("error.must_target_taunt")


def attack_targets(state: GameState, seat: int, attacker_uid: str) -> list[str]:
    """Enemy units the attacker can reach: same tier or one tier higher."""
    try:
        check_attack(state, seat, attacker_uid)
    except IllegalAction:
        return []
    found = _tier_of(state, attacker_uid)
    assert found is not None
    tier, attacker = found[1], found[2]
    targets: list[str] = []
    for player in state.players:
        if player.seat == seat:
            continue
        reachable = [(t, u) for t, u in state.units_of(player.seat) if t in (tier, tier + 1) or attacker.temp_any_tier]
        targets += [u.uid for _, u in apply_taunt(reachable)]
    return targets


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
    mods = catalog.card(attacker.def_id).modifiers
    target_mods = catalog.card(target.def_id).modifiers
    hit = [target]
    cleave = next((m["cleave"] for m in mods if "cleave" in m), None)
    if cleave is not None:  # e.g. 803 "on attack: deal dmg to all units in a row"
        tier = _tier_of(state, target_uid)[1]
        hit = [u for p in state.players if p.seat != seat for t, u in state.units_of(p.seat) if t == tier]
    for unit in hit:
        damage_unit(ctx, unit.uid, attacker.attack_value)
    statuses = [s_ for s_, key in (("stun", "stun_on_attack"), ("freeze", "freeze_on_attack")) if any(m.get(key) for m in mods)]
    if isinstance(cleave, dict) and "freeze_if" in cleave:
        cond = cleave["freeze_if"]
        piles = (*state.players[seat].discard, *state.players[seat].in_play)
        if sum(1 for c in piles if cond["element"] in catalog.card(c.def_id).elements) >= cond["min"]:
            statuses.append("freeze")
    for unit in hit:
        if find_unit(state, unit.uid):
            for status in statuses:  # "targets attacked by this unit are stunned / frozen"
                unit.status[status] += 1
                events.append(Event("log.status_added", {"card": unit.def_id, "owner": unit.owner, "status": status, "count": 1}))
    thorns = sum(int(m.get("thorns", 0)) for m in target_mods)
    thorns += sum(int(m.get("ally_thorns", 0)) for _, u in state.units_of(target.owner) for m in catalog.card(u.def_id).modifiers)
    if thorns and find_unit(state, attacker_uid):  # "deal 1 dmg to all units that attack this unit"
        damage_unit(EffectContext(state, catalog, target.owner, target, events), attacker_uid, thorns)
    if ctx.kills:
        for marked_seat, vp in attacker.temp_kill_vp:  # e.g. 761: "if this attack kills any unit, gain 1 VP"
            state.players[marked_seat].vp += vp
            events.append(Event("log.gain_vp", {"seat": marked_seat, "amount": vp}))
        player = state.players[seat]
        vp = sum(m["amount"] for m in player.turn_modifiers if m["kind"] == "vp_per_attack_kill")
        if vp:
            player.vp += vp
            events.append(Event("log.gain_vp", {"seat": seat, "amount": vp}))
        nodes = catalog.card(attacker.def_id).triggers.get("on_kill", ())
        if nodes:
            resolve_effects(ctx, nodes)
