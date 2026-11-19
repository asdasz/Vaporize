"""Keeping class resource on a unit (`resource_bank` modifier, e.g. 143 "put and take any gold on this unit").

During your turn you may move resource between your pool and the unit, any number of times. At the end of
your turn the stored amount doubles (engine/turn.py) and isn't taxed. It's lost when the unit leaves the board.
"""

from __future__ import annotations

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.state import GameState


def is_bank(catalog: Catalog, unit: CardInstance) -> bool:
    return any(m.get("resource_bank") for m in catalog.card(unit.def_id).modifiers)


def bank_limits(state: GameState, catalog: Catalog, seat: int, unit: CardInstance) -> tuple[int, int]:
    """(most you can put on the unit, most you can take back). Taking can't push you past the class hard max."""
    player = state.players[seat]
    cap = catalog.cls(player.class_id).resource.hard_max
    take = unit.stored if cap is None else max(0, min(unit.stored, cap - player.resource))
    return player.resource, take


def check_bank(state: GameState, catalog: Catalog, seat: int, unit_uid: str, amount: int) -> CardInstance:
    unit = next((u for _, u in state.units_of(seat) if u.uid == unit_uid), None)
    if unit is None:
        raise IllegalAction("error.not_your_unit")
    if not is_bank(catalog, unit):
        raise IllegalAction("error.not_a_bank")
    put_max, take_max = bank_limits(state, catalog, seat, unit)
    if amount == 0 or amount > put_max or -amount > take_max:
        raise IllegalAction("error.invalid_amount")
    return unit


def bank(state: GameState, catalog: Catalog, seat: int, unit_uid: str, amount: int, events: list[Event]) -> CardInstance:
    """Positive `amount`: put resource on the unit. Negative: take it back."""
    unit = check_bank(state, catalog, seat, unit_uid, amount)
    player = state.players[seat]
    player.resource -= amount
    unit.stored += amount
    key = catalog.cls(player.class_id).resource.key
    events.append(Event("log.bank_put" if amount > 0 else "log.bank_take", {"seat": seat, "card": unit.def_id, "amount": abs(amount), "resource": key}))
    return unit


def legal_bank(state: GameState, catalog: Catalog, seat: int) -> dict[str, dict[str, int]]:
    out = {}
    for _, unit in state.units_of(seat):
        if is_bank(catalog, unit):
            put_max, take_max = bank_limits(state, catalog, seat, unit)
            out[unit.uid] = {"put": put_max, "take": take_max, "stored": unit.stored}
    return out
