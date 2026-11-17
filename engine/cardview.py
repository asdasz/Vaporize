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
    if cdef.is_unit:
        view.update(
            attack=card.attack_value if card.fixed_attack is not None else cdef.attack,
            health=card.fixed_health if card.fixed_health is not None else cdef.health,
            hp=card.current_hp if card.current_hp is not None else cdef.health,
            status=dict(card.status),
            tapped=card.tapped,
            token=card.is_token,
        )
    return view
