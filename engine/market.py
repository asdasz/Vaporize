"""Markets: buying and refreshing (rulebook: The shared market, Private markets)."""

from __future__ import annotations

from engine.catalog import Catalog
from engine.errors import IllegalAction
from engine.events import Event
from engine.cards import CardInstance
from engine.rules import PRIVATE_MARKET_SIZE, SHARED_MARKET_SIZE, SHARED_PRICE_MODIFIERS
from engine.state import GameState, MarketState

MARKETS = ("shared", "private", "basic")  # basic = the basic supply pile (buy only, no refresh)
REFRESH_COST = 1


def get_market(state: GameState, seat: int, market: str) -> MarketState:
    """The shared market or the player's private market (not the basic pile)."""
    if market == "shared":
        return state.shared_market
    if market == "private":
        return state.players[seat].private_market
    raise IllegalAction("error.unknown_market")


def basic_price(state: GameState, catalog: Catalog) -> int | None:
    top = state.basic_supply.top()
    return catalog.card(top.def_id).cost if top else None


def price(state: GameState, catalog: Catalog, seat: int, market: str, slot: int) -> int | None:
    if market == "basic":
        return basic_price(state, catalog)
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


def _card_at(state: GameState, seat: int, market: str, slot: int) -> CardInstance | None:
    if market == "basic":
        return state.basic_supply.top()
    m = get_market(state, seat, market)
    return m.row.slots[slot] if 0 <= slot < len(m.row) else None


def check_buy(state: GameState, catalog: Catalog, seat: int, market: str, slot: int, pay: str = "inf") -> int:
    """Returns the inf to pay (0 when paying with VP)."""
    cost = price(state, catalog, seat, market, slot)
    if cost is None:
        raise IllegalAction("error.empty_slot")
    if pay == "vp":
        card = _card_at(state, seat, market, slot)
        alt = catalog.card(card.def_id).alt_cost if card else None
        if not alt:
            raise IllegalAction("error.no_alt_cost")
        if state.players[seat].vp < alt["lose_vp"]:
            raise IllegalAction("error.not_enough_vp", vp=alt["lose_vp"])
        return 0
    if pay != "inf":
        raise IllegalAction("error.unknown_payment")
    if state.players[seat].inf < cost:
        raise IllegalAction("error.not_enough_inf", cost=cost)
    return cost


def _pay(state: GameState, catalog: Catalog, seat: int, card: CardInstance, cost: int, pay: str, market: str, events: list[Event]) -> None:
    player = state.players[seat]
    if pay == "vp":
        lose = (catalog.card(card.def_id).alt_cost or {})["lose_vp"]
        player.vp -= lose
        events.append(Event("log.card_bought_vp", {"seat": seat, "card": card.def_id, "vp": lose, "market": market}))
    else:
        player.inf -= cost
        events.append(Event("log.card_bought", {"seat": seat, "card": card.def_id, "price": cost, "market": market}))


def buy(
    state: GameState, catalog: Catalog, seat: int, market: str, slot: int, events: list[Event], pay: str = "inf"
) -> None:
    """Pay the price (or the card's alternative VP cost); the card goes to your discard pile and a new card
    is revealed in its place."""
    cost = check_buy(state, catalog, seat, market, slot, pay)
    player = state.players[seat]
    if market == "basic":  # always the top card of the basic pile, printed price, nothing revealed
        card = state.basic_supply.draw()
        card.owner = seat
        _pay(state, catalog, seat, card, cost, pay, market, events)
        player.discard.put_bottom(card)
        return
    m = get_market(state, seat, market)
    card = m.row.slots[slot]
    assert card is not None
    m.row.slots[slot] = None
    card.owner = seat
    _pay(state, catalog, seat, card, cost, pay, market, events)
    player.discard.put_bottom(card)
    reveal(state, m, market, slot, events)


def refresh_cost(state: GameState, seat: int, market: str) -> int:
    """The first shared-market refresh each turn is free; every other refresh costs 1 inf."""
    if market == "shared" and not state.players[seat].free_refresh_used:
        return 0
    return REFRESH_COST


def check_refresh(state: GameState, seat: int, market: str) -> int:
    if market == "basic":
        raise IllegalAction("error.cannot_refresh_basic")
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
    events.append(Event("log.market_refreshed", {"seat": seat, "market": market, "cost": cost}))
    slide(state, m, market, events)


def slide(state: GameState, m: MarketState, name: str, events: list[Event]) -> None:
    """The refresh move: rightmost card to the removed pile, others one spot right, new card on the left."""
    slots = m.row.slots
    if slots[-1] is not None:
        m.removed.put_bottom(slots[-1])
    for i in range(len(slots) - 1, 0, -1):
        slots[i] = slots[i - 1]
    slots[0] = None
    reveal(state, m, name, 0, events)


def legal_market(state: GameState, catalog: Catalog, seat: int) -> dict[str, object]:
    out: dict[str, object] = {}
    basic = basic_price(state, catalog)
    out["basic_buy"] = basic is not None and basic <= state.players[seat].inf
    alt: list[dict[str, object]] = []
    for name, slots in (("shared", range(SHARED_MARKET_SIZE)), ("private", range(PRIVATE_MARKET_SIZE)), ("basic", range(1))):
        for i in slots:
            try:
                check_buy(state, catalog, seat, name, i, "vp")
            except IllegalAction:
                continue
            card = _card_at(state, seat, name, i)
            assert card is not None
            alt.append({"market": name, "slot": i, "vp": (catalog.card(card.def_id).alt_cost or {})["lose_vp"]})
    out["alt_buy"] = alt
    for name in ("shared", "private"):
        m = get_market(state, seat, name)
        out[f"{name}_buy"] = [
            i for i in range(len(m.row)) if (c := price(state, catalog, seat, name, i)) is not None and c <= state.players[seat].inf
        ]
        try:
            out[f"{name}_refresh"] = check_refresh(state, seat, name)
        except IllegalAction:
            out[f"{name}_refresh"] = None
    return out
