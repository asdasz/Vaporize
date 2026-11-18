"""JSON-ready description of a card instance (used by views and prompts)."""

from __future__ import annotations

from typing import Any

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.elements import elements_of


def card_view(card: CardInstance, catalog: Catalog) -> dict[str, Any]:
    cdef = catalog.card(card.def_id)
    view: dict[str, Any] = {
        "uid": card.uid,
        "id": cdef.id,
        "number": cdef.number,
        "type": cdef.type,
        "cost": cdef.cost,
        "elements": list(elements_of(card, catalog)),
        "owner": card.owner,
    }
    if cdef.alt_cost:
        view["alt_cost"] = dict(cdef.alt_cost)
    if cdef.hand_eot:
        view["hand_eot"] = dict(cdef.hand_eot)
    if cdef.is_unit:
        view.update(
            attack=card.attack_value if card.fixed_attack is not None else cdef.attack,
            health=card.fixed_health if card.fixed_health is not None else cdef.health,
            hp=card.current_hp if card.current_hp is not None else cdef.health,
            status=dict(card.status),
            tapped=card.tapped,
            attacks_left=max(0, attacks_allowed(card, catalog) - card.attacks_made),
            token=card.is_token,
        )
    return view


def attacks_allowed(card: CardInstance, catalog: Catalog) -> int:
    """1 attack per turn, plus static `extra_attacks` modifiers and extra attacks granted this turn."""
    static = sum(int(m.get("extra_attacks", 0)) for m in catalog.card(card.def_id).modifiers)
    return 1 + static + card.temp_extra_attacks
