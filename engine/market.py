"""Markets: buying and refreshing (rulebook: The shared market, Private markets)."""

from __future__ import annotations

from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.rules import SHARED_PRICE_MODIFIERS
from engine.state import GameState, MarketState

MARKETS = ("shared", "private")
REFRESH_COST = 1


def get_market(state: GameState, seat: int, market: str) -> MarketState:
    if market == "shared":
        return state.shared_market
    if market == "private":
        return state.players[seat].private_market
    raise IllegalAction("error.unknown_market")


def price(state: GameState, catalog: Catalog, seat: int, market: str, slot: int) -> int | None:
    m = get_market(state, seat, market)
    if not 0 <= slot < len(m.row) or m.row.slots[slot] is None:
        return None
    card = m.row.slots[slot]
    assert card is not None
    mod = SHARED_PRICE_MODIFIERS[slot] if market == "shared" else 0
    return max(0, catalog.card(card.def_id).cost + mod)


def reveal(state: GameState, market: MarketState, name: str, slot: int, events: list[Event]) -> None:
    """Fill an empty slot from the market deck (reshuffling the removed pile if the deck is empty)."""
    if market.deck.is_empty() and not market.removed.is_empty():
        market.deck.cards = market.removed.take_all()
        market.deck.shuffle(state.rng)
        events.append(Event("log.market_reshuffled", {"market": name}))
    if market.deck.is_empty() or market.row.slots[slot] is not None:
        return
    card = market.deck.draw()
    market.row.place(card, slot)
    events.append(Event("log.market_revealed", {"market": name, "card": card.def_id}))


def check_buy(state: GameState, catalog: Catalog, seat: int, market: str, slot: int) -> int:
    cost = price(state, catalog, seat, market, slot)
    if cost is None:
        raise IllegalAction("error.empty_slot")
    if state.players[seat].inf < cost:
        raise IllegalAction("error.not_enough_inf", cost=cost)
    return cost


def buy(state: GameState, catalog: Catalog, seat: int, market: str, slot: int, events: list[Event]) -> None:
    """Pay the price; the card goes to your discard pile and a new card is revealed in its place."""
    cost = check_buy(state, catalog, seat, market, slot)
    m = get_market(state, seat, market)
    card = m.row.slots[slot]
    assert card is not None
    m.row.slots[slot] = None
    card.owner = seat
    player = state.players[seat]
    player.inf -= cost
    player.discard.put_bottom(card)
    events.append(Event("log.card_bought", {"seat": seat, "card": card.def_id, "price": cost, "market": market}))
    reveal(state, m, market, slot, events)


def refresh_cost(state: GameState, seat: int, market: str) -> int:
    """The first shared-market refresh each turn is free; every other refresh costs 1 inf."""
    if market == "shared" and not state.players[seat].free_refresh_used:
        return 0
    return REFRESH_COST


def check_refresh(state: GameState, seat: int, market: str) -> int:
    m = get_market(state, seat, market)
    if all(c is None for c in m.row.slots) and m.deck.is_empty() and m.removed.is_empty():
        raise IllegalAction("error.empty_market")
    cost = refresh_cost(state, seat, market)
    if state.players[seat].inf < cost:
        raise IllegalAction("error.not_enough_inf", cost=cost)
    return cost


def refresh(state: GameState, seat: int, market: str, events: list[Event]) -> None:
    """Remove the rightmost card from the game, slide the others right, reveal a new leftmost card."""
    cost = check_refresh(state, seat, market)
    m = get_market(state, seat, market)
    player = state.players[seat]
    player.inf -= cost
    if market == "shared" and cost == 0:
        player.free_refresh_used = True
    slots = m.row.slots
    if slots[-1] is not None:
        m.removed.put_bottom(slots[-1])
    for i in range(len(slots) - 1, 0, -1):
        slots[i] = slots[i - 1]
    slots[0] = None
    events.append(Event("log.market_refreshed", {"seat": seat, "market": market, "cost": cost}))
    reveal(state, m, market, 0, events)


def legal_market(state: GameState, catalog: Catalog, seat: int) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in MARKETS:
        m = get_market(state, seat, name)
        out[f"{name}_buy"] = [
            i for i in range(len(m.row)) if (c := price(state, catalog, seat, name, i)) is not None and c <= state.players[seat].inf
        ]
        try:
            out[f"{name}_refresh"] = check_refresh(state, seat, name)
        except IllegalAction:
            out[f"{name}_refresh"] = None
    return out
