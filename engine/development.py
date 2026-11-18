"""Developing units: moving a unit up one tier (rulebook: Units, tiers and combat)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.state import GameState
from engine.zones import SlotRow, Zone

MAX_TIER = 4


@dataclass(frozen=True)
class DevelopOption:
    uid: str
    from_tier: int
    to_tier: int
    cost: int


def unit_tier(state: GameState, seat: int, uid: str) -> tuple[int, CardInstance] | None:
    for tier, unit in state.units_of(seat):
        if unit.uid == uid:
            return tier, unit
    return None


def _row(state: GameState, seat: int, tier: int) -> SlotRow:
    return state.tier4 if tier == MAX_TIER else state.players[seat].tiers[tier]


def _container(state: GameState, seat: int, tier: int, unit: CardInstance) -> SlotRow | Zone:
    player = state.players[seat]
    if player.tokens.find(unit.uid):
        return player.tokens
    return _row(state, seat, tier)


def check_develop(
    state: GameState, catalog: Catalog, seat: int, uid: str, cost_override: int | None = None
) -> DevelopOption:
    """Validate developing `uid` by one tier for `seat`. Raises IllegalAction."""
    found = unit_tier(state, seat, uid)
    if found is None:
        raise IllegalAction("error.not_your_unit")
    tier, unit = found
    if tier >= MAX_TIER:
        raise IllegalAction("error.max_tier")
    if unit.status["freeze"] > 0:
        raise IllegalAction("error.unit_frozen")
    to_tier = tier + 1
    if not _row(state, seat, to_tier).has_free():
        raise IllegalAction("error.tier_full", tier=to_tier)
    rule_cost = catalog.cls(state.players[seat].class_id).tiers[to_tier].develop_cost or 0
    cost = rule_cost if cost_override is None else cost_override
    if cost_override is None:
        cost = max(0, cost - develop_discount(state, catalog, seat))
    if state.players[seat].inf < cost:
        raise IllegalAction("error.not_enough_inf", cost=cost)
    return DevelopOption(uid, tier, to_tier, cost)


def develop_discount(state: GameState, catalog: Catalog, seat: int) -> int:
    """Static discounts (units with `develop_discount`) + "your next development costs 1 less per prepare"."""
    player = state.players[seat]
    total = sum(int(m.get("develop_discount", 0)) for _, u in state.units_of(seat) for m in catalog.card(u.def_id).modifiers)
    if any(m["kind"] == "next_develop_discount_per_prepare" for m in player.turn_modifiers):
        total += player.prepares_this_turn
    return total


def develop_unit(state: GameState, catalog: Catalog, seat: int, option: DevelopOption, events: list[Event]) -> None:
    """Pay and move the unit up. Developing doesn't heal or untap it."""
    unit = unit_tier(state, seat, option.uid)
    assert unit is not None
    _, card = unit
    _container(state, seat, option.from_tier, card).take(card.uid)
    _row(state, seat, option.to_tier).place(card)
    player = state.players[seat]
    player.inf -= option.cost
    # "your next development costs less" is used up by this development
    player.turn_modifiers = [m for m in player.turn_modifiers if m["kind"] != "next_develop_discount_per_prepare"]
    events.append(
        Event("log.unit_developed", {"seat": seat, "card": card.def_id, "tier": option.to_tier, "cost": option.cost})
    )


def legal_develops(state: GameState, catalog: Catalog, seat: int) -> list[DevelopOption]:
    options = []
    for _, unit in state.units_of(seat):
        try:
            options.append(check_develop(state, catalog, seat, unit.uid))
        except IllegalAction:
            continue
    return options


def eot_vp(state: GameState, catalog: Catalog, seat: int) -> int:
    """VP the player's units would score at the end of their turn right now."""
    tiers = catalog.cls(state.players[seat].class_id).tiers
    return sum(tiers[tier].vp for tier, _ in state.units_of(seat))
