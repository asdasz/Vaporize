"""Creating a new game (rulebook: Setup)."""

from __future__ import annotations

import random

from engine.cards import CardDef, CardInstance
from engine.catalog import Catalog
from engine.drawing import draw_cards
from engine.events import Event
from engine.rules import MAX_PLAYERS, MIN_PLAYERS, PRIVATE_MARKET_SIZE, SHARED_MARKET_SIZE, STARTING_HAND
from engine.state import GameState, MarketState, PlayerState
from engine.turn import start_turn
from engine.zones import SlotRow, Zone


def _instances(state: GameState, defs: list[CardDef], owner: int) -> list[CardInstance]:
    return [CardInstance(uid=state.new_uid(), def_id=d.id, owner=owner) for d in defs for _ in range(d.copies)]


def _reveal(market: MarketState) -> None:
    for i in range(len(market.row)):
        if market.row.slots[i] is None and not market.deck.is_empty():
            market.row.place(market.deck.draw(), i)


def new_game(catalog: Catalog, seats: list[tuple[str, str]], seed: int) -> tuple[GameState, list[Event]]:
    """Create a game. `seats` is a list of (player name, class id) in seat order."""
    if not MIN_PLAYERS <= len(seats) <= MAX_PLAYERS:
        raise ValueError(f"a game needs {MIN_PLAYERS}-{MAX_PLAYERS} players")
    events: list[Event] = []
    state = GameState(
        players=[],
        shared_market=MarketState(Zone("shared.deck"), SlotRow("shared.row", SHARED_MARKET_SIZE), Zone("shared.removed")),
        basic_supply=Zone("basic"),
        tier4=SlotRow("tier4", len(seats) - 1),
        rng=random.Random(seed),
        seed=seed,
    )
    for seat, (name, class_id) in enumerate(seats):
        cdef = catalog.cls(class_id)
        player = PlayerState(
            seat=seat,
            name=name,
            class_id=class_id,
            deck=Zone(f"p{seat}.deck"),
            hand=Zone(f"p{seat}.hand"),
            in_play=Zone(f"p{seat}.in_play"),
            discard=Zone(f"p{seat}.discard"),
            removed=Zone(f"p{seat}.removed"),
            tokens=Zone(f"p{seat}.tokens"),
            private_market=MarketState(
                Zone(f"p{seat}.private.deck"),
                SlotRow(f"p{seat}.private.row", PRIVATE_MARKET_SIZE),
                Zone(f"p{seat}.private.removed"),
            ),
            tiers={t: SlotRow(f"p{seat}.tier{t}", cdef.tiers[t].spots or 0) for t in (1, 2, 3)},
            resource=cdef.resource.start,
        )
        player.deck.cards = _instances(state, catalog.starter_cards(class_id), seat)
        player.deck.shuffle(state.rng)
        player.private_market.deck.cards = _instances(state, catalog.private_cards(class_id), seat)
        player.private_market.deck.shuffle(state.rng)
        _reveal(player.private_market)
        state.players.append(player)

    state.shared_market.deck.cards = _instances(state, catalog.shared_cards(), -1)
    state.shared_market.deck.shuffle(state.rng)
    _reveal(state.shared_market)
    state.basic_supply.cards = _instances(state, catalog.basic_cards(), -1)

    for seat in range(len(seats)):
        draw_cards(state, seat, STARTING_HAND, events)

    state.first_player = state.rng.randrange(len(seats))
    state.current = state.first_player
    events.append(Event("log.game_started", {"first_player": state.first_player}))
    start_turn(state, catalog, events)
    return state, events
