"""In-memory hot-seat games for development. Framework-free so it can be tested directly.

Will be replaced by real rooms (lobby, join codes, WebSockets) in a later PR.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from engine.actions import Action, EndTurn, IllegalAction, PlayCard, apply_action
from engine.catalog import Catalog
from engine.events import Event
from engine.setup import new_game
from engine.state import GameState
from engine.view import build_view
from server.codes import generate_code

LOG_LIMIT = 60


class GameNotFound(Exception):
    pass


@dataclass
class DevGame:
    state: GameState
    log: list[dict[str, Any]] = field(default_factory=list)

    def record(self, events: list[Event]) -> None:
        self.log.extend(e.to_dict() for e in events)
        del self.log[:-LOG_LIMIT]


def parse_action(payload: dict[str, Any]) -> Action:
    kind = payload.get("type")
    seat = int(payload.get("seat", -1))
    if kind == "play_card":
        return PlayCard(seat=seat, card_uid=str(payload.get("card_uid")))
    if kind == "end_turn":
        return EndTurn(seat=seat)
    raise IllegalAction("error.unknown_action")


class DevGames:
    def __init__(self, catalog: Catalog, class_id: str = "mage") -> None:
        self.catalog = catalog
        self.class_id = class_id
        self.games: dict[str, DevGame] = {}
        self._rng = random.SystemRandom()

    def create(self, players: int, seed: int | None = None) -> str:
        seed = seed if seed is not None else self._rng.randrange(2**31)
        seats = [(f"Player {i + 1}", self.class_id) for i in range(players)]
        state, events = new_game(self.catalog, seats, seed)
        game_id = generate_code(random.Random(seed), self.games)
        game = DevGame(state)
        game.record(events)
        self.games[game_id] = game
        return game_id

    def _get(self, game_id: str) -> DevGame:
        try:
            return self.games[game_id.upper()]
        except KeyError:
            raise GameNotFound(game_id) from None

    def view(self, game_id: str, seat: int) -> dict[str, Any]:
        game = self._get(game_id)
        view = build_view(game.state, self.catalog, seat)
        view["game_id"] = game_id.upper()
        view["log"] = list(game.log)
        return view

    def act(self, game_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        game = self._get(game_id)
        try:
            action = parse_action(payload)
            game.state, events = apply_action(game.state, self.catalog, action)
        except IllegalAction as exc:
            return {"ok": False, "error": {"key": exc.key, "params": exc.params}}
        game.record(events)
        return {"ok": True, "events": [e.to_dict() for e in events]}
