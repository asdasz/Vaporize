"""Builds the redacted, JSON-ready view of the game for one player."""

from __future__ import annotations

from collections import Counter
from typing import Any

from engine.actions import legal_plays
from engine.cardview import card_view
from engine.catalog import Catalog
from engine.development import eot_vp, legal_develops
from engine.element_swap import has_element_swap, swap_available, swap_options
from engine.removal import removable_cards
from engine.attacks import legal_attacks
from engine.bank import legal_bank
from engine.context import EffectContext
from engine.effects.economy import tax_preview
from engine.market import basic_price, legal_market, refresh_cost
from engine.rules import ELEMENTS, MIN_HAND, SHARED_PRICE_MODIFIERS
from engine.state import GameState, MarketState, PlayerState
from engine.zones import SlotRow


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
        "eot_vp": eot_vp(state, catalog, player.seat),
        "inf": player.inf,
        "resource": {
            "key": cdef.resource.key,
            "value": player.resource,
            "limit": cdef.resource.limit,
            "max": cdef.resource.hard_max,
        },
        "removal_cost": cdef.removal_cost(player.removal_index),
        "develop_inf": player.develop_inf,
        "any_tier_attacks": player.any_tier_attacks,
        "tax": _tax(state, catalog, player),
        "hand_count": len(player.hand),
        "hand": [card_view(c, catalog) for c in player.hand] if player.seat == viewer else None,
        "locked_cards": list(player.locked_cards),  # revealed cards are public anyway
        "deck_count": len(player.deck),
        "discard": [card_view(c, catalog) for c in player.discard],
        "in_play": [card_view(c, catalog) for c in player.in_play],
        "removed_count": len(player.removed),
        "removed": [card_view(c, catalog) for c in player.removed],
        "played_elements": {e: played.get(e, 0) for e in ELEMENTS},
        "played_count": len(player.played_this_turn),
        "turn_modifiers": [dict(m) for m in player.turn_modifiers],
        "free_refresh_used": player.free_refresh_used,
        "tiers": {str(t): _row(row, catalog) for t, row in player.tiers.items()},
        "tokens": [card_view(c, catalog) for c in player.tokens],
        "tier_rules": {
            str(t): {"spots": r.spots, "develop_cost": r.develop_cost, "vp": r.vp} for t, r in cdef.tiers.items()
        },
        "private_market": _market(player.private_market, catalog, None),
    }


def _tax(state: GameState, catalog: Catalog, player: PlayerState) -> int | None:
    """End-of-turn tax the player would pay right now; None for classes without tax."""
    cdef = catalog.cls(player.class_id)
    taxes = [e for p in cdef.passives if p.get("trigger") == "eot" for e in p.get("effects", []) if e.get("do") == "pay_tax"]
    if not taxes:
        return None
    return tax_preview(EffectContext(state, catalog, player.seat, None, []), int(taxes[0].get("per", 4)))


def _pending(state: GameState, catalog: Catalog, viewer: int) -> dict[str, Any] | None:
    """The pending choice. Only the acting player sees the prompt (it may show hidden cards)."""
    pending = state.pending
    if pending is None:
        return None
    card = state.players[pending.seat].hand.find(pending.card_uid) if pending.card_uid else None
    if card is None and pending.kind == "attack":  # the attacking unit
        card = next((u for _, u in state.units_of(pending.seat) if u.uid == pending.card_uid), None)
    view: dict[str, Any] = {"seat": pending.seat, "card": card_view(card, catalog) if card else None, "kind": pending.kind}
    if viewer == pending.seat:
        view["prompt"] = pending.prompt.to_dict()
        view["step"] = len(pending.answers)
    return view


def build_view(state: GameState, catalog: Catalog, viewer: int) -> dict[str, Any]:
    if not 0 <= viewer < len(state.players):
        raise ValueError(f"no seat {viewer}")
    me = state.players[viewer]
    my_turn = state.phase == "actions" and state.current == viewer
    free = my_turn and state.pending is None  # no choice waiting
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
        "basic_supply": {
            "count": len(state.basic_supply),
            "card": card_view(state.basic_supply.top(), catalog) if state.basic_supply.top() else None,
            "price": basic_price(state, catalog),
        },
        "pending": _pending(state, catalog, viewer),
        "legal": {
            "playable": legal_plays(state, catalog, viewer) if free else [],
            "plays_left": max(0, len(me.hand) - MIN_HAND) if my_turn else 0,
            "can_end_turn": free,
            "removable": removable_cards(state, catalog, viewer) if free else [],
            "element_swap": {
                "has": has_element_swap(state, catalog, viewer),
                "available": free and swap_available(state, catalog, viewer),
                "options": {
                    c.uid: opts
                    for c in me.hand
                    if free and swap_available(state, catalog, viewer) and (opts := swap_options(catalog, c))
                },
            },
            "attacks": legal_attacks(state, viewer) if free else {},
            "market": legal_market(state, catalog, viewer) if free else {},
            "shared_refresh_cost": refresh_cost(state, viewer, "shared"),
            "develop": {
                o.uid: {"cost": o.cost, "to": o.to_tier} for o in (legal_develops(state, catalog, viewer) if free else [])
            },
            # 145: units that can also be developed paying the class resource
            "develop_resource": {
                o.uid: {"cost": o.cost, "to": o.to_tier}
                for o in (legal_develops(state, catalog, viewer, pay="resource") if free else [])
            },
            "bank": legal_bank(state, catalog, viewer) if free else {},
            "can_undo": free and bool(state.undo_stack),
            "undo_card": state.undo_stack[-1].card_id if free and state.undo_stack else None,
            "undo_count": len(state.undo_stack) if free else 0,
        },
        "rules": {"min_hand": MIN_HAND},
    }
