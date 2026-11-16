"""Builds the redacted, JSON-ready view of the game for one player."""

from __future__ import annotations

from collections import Counter
from typing import Any

from engine.actions import legal_plays
from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.elements import elements_of
from engine.rules import ELEMENTS, MIN_HAND, SHARED_PRICE_MODIFIERS
from engine.state import GameState, MarketState, PlayerState
from engine.zones import SlotRow


def card_view(card: CardInstance, catalog: Catalog) -> dict[str, Any]:
    cdef = catalog.card(card.def_id)
    view: dict[str, Any] = {
        "uid": card.uid,
        "id": cdef.id,
        "type": cdef.type,
        "cost": cdef.cost,
        "elements": list(elements_of(card, catalog)),
        "owner": card.owner,
    }
    if cdef.is_unit:
        view.update(
            attack=card.fixed_attack if card.fixed_attack is not None else cdef.attack,
            health=card.fixed_health if card.fixed_health is not None else cdef.health,
            hp=card.current_hp if card.current_hp is not None else cdef.health,
            status=dict(card.status),
            tapped=card.tapped,
            token=card.is_token,
        )
    return view


def _row(row: SlotRow, catalog: Catalog) -> list[dict[str, Any] | None]:
    return [card_view(c, catalog) if c else None for c in row.slots]


def _market(market: MarketState, catalog: Catalog, modifiers: tuple[int, ...] | None) -> dict[str, Any]:
    row = []
    for i, card in enumerate(market.row.slots):
        if card is None:
            row.append(None)
            continue
        mod = modifiers[i] if modifiers else 0
        row.append({"card": card_view(card, catalog), "modifier": mod, "price": max(0, catalog.card(card.def_id).cost + mod)})
    return {"row": row, "deck_count": len(market.deck), "removed_count": len(market.removed)}


def _player(state: GameState, catalog: Catalog, player: PlayerState, viewer: int) -> dict[str, Any]:
    cdef = catalog.cls(player.class_id)
    played = Counter(e for p in player.played_this_turn for e in p.elements)
    return {
        "seat": player.seat,
        "name": player.name,
        "class_id": player.class_id,
        "vp": player.vp,
        "inf": player.inf,
        "resource": {
            "key": cdef.resource.key,
            "value": player.resource,
            "limit": cdef.resource.limit,
            "max": cdef.resource.hard_max,
        },
        "removal_cost": cdef.removal_cost(player.removal_index),
        "hand_count": len(player.hand),
        "hand": [card_view(c, catalog) for c in player.hand] if player.seat == viewer else None,
        "deck_count": len(player.deck),
        "discard": [card_view(c, catalog) for c in player.discard],
        "in_play": [card_view(c, catalog) for c in player.in_play],
        "removed_count": len(player.removed),
        "played_elements": {e: played.get(e, 0) for e in ELEMENTS},
        "played_count": len(player.played_this_turn),
        "free_refresh_used": player.free_refresh_used,
        "tiers": {str(t): _row(row, catalog) for t, row in player.tiers.items()},
        "tokens": [card_view(c, catalog) for c in player.tokens],
        "tier_rules": {
            str(t): {"spots": r.spots, "develop_cost": r.develop_cost, "vp": r.vp} for t, r in cdef.tiers.items()
        },
        "private_market": _market(player.private_market, catalog, None),
    }


def build_view(state: GameState, catalog: Catalog, viewer: int) -> dict[str, Any]:
    if not 0 <= viewer < len(state.players):
        raise ValueError(f"no seat {viewer}")
    me = state.players[viewer]
    my_turn = state.phase == "actions" and state.current == viewer
    return {
        "you": viewer,
        "round": state.round,
        "current": state.current,
        "first_player": state.first_player,
        "phase": state.phase,
        "winners": list(state.winners),
        "players": [_player(state, catalog, p, viewer) for p in state.players],
        "tier4": _row(state.tier4, catalog),
        "shared_market": _market(state.shared_market, catalog, SHARED_PRICE_MODIFIERS),
        "legal": {
            "playable": legal_plays(state, catalog, viewer) if my_turn else [],
            "plays_left": max(0, len(me.hand) - MIN_HAND) if my_turn else 0,
            "can_end_turn": my_turn,
        },
        "rules": {"min_hand": MIN_HAND},
    }
