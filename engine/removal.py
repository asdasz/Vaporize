"""Removing cards from your deck for good (rulebook: Remove a card).

A card in your hand, played this turn (`in_play`) or in the discard pile can be removed.
Effects of a played card that already happened stay (inf gained, elements counted as played this turn).
Removing from the hand respects the 2-card minimum.
"""

from __future__ import annotations

from engine.cards import CardInstance
from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.rules import MIN_HAND
from engine.state import GameState
from engine.zones import Zone


def removal_cost(state: GameState, catalog: Catalog, seat: int) -> int | None:
    """Cost of the next removal on the player's track, or None when the track is used up."""
    player = state.players[seat]
    return catalog.cls(player.class_id).removal_cost(player.removal_index)


def _source_zone(state: GameState, seat: int, uid: str) -> Zone | None:
    player = state.players[seat]
    for zone in (player.hand, player.in_play, player.discard):
        if zone.find(uid):
            return zone
    return None


def check_remove(state: GameState, catalog: Catalog, seat: int, uid: str) -> tuple[Zone, int]:
    zone = _source_zone(state, seat, uid)
    if zone is None:
        raise IllegalAction("error.card_not_removable")
    if zone is state.players[seat].hand and len(zone) <= MIN_HAND:
        raise IllegalAction("error.min_hand", min=MIN_HAND)
    cost = removal_cost(state, catalog, seat)
    if cost is None:
        raise IllegalAction("error.removal_track_full")
    if state.players[seat].inf < cost:
        raise IllegalAction("error.not_enough_inf", cost=cost)
    return zone, cost


def remove_card(state: GameState, catalog: Catalog, seat: int, uid: str, events: list[Event]) -> CardInstance:
    zone, cost = check_remove(state, catalog, seat, uid)
    player = state.players[seat]
    card = zone.take(uid)
    player.removed.put_bottom(card)
    player.inf -= cost
    player.removal_index += 1
    events.append(Event("log.card_removed", {"seat": seat, "card": card.def_id, "cost": cost}))
    return card


def removable_cards(state: GameState, catalog: Catalog, seat: int) -> list[str]:
    player = state.players[seat]
    cost = removal_cost(state, catalog, seat)
    if cost is None or player.inf < cost:
        return []
    hand = list(player.hand) if len(player.hand) > MIN_HAND else []
    return [c.uid for c in (*hand, *player.in_play, *player.discard)]
