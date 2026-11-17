"""Hot-seat games for development. Framework-free so it can be tested directly.

Games can be saved to a local file so they survive `uvicorn --reload` restarts.
Will be replaced by real rooms (lobby, join codes, WebSockets) in a later PR.
"""

from __future__ import annotations

import logging
import pickle
import random
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from engine.actions import (
    Action,
    Attack,
    Buy,
    CancelChoice,
    CancelTurn,
    Develop,
    EndTurn,
    IllegalAction,
    PlayCard,
    Refresh,
    RemoveCard,
    Respond,
    Undo,
    apply_action,
)
from engine.catalog import Catalog
from engine.events import Event
from engine.setup import new_game
from engine.state import GameState
from engine.view import build_view
from server.codes import generate_code

LOG_LIMIT = 60
# Bump when engine state classes change, so old save files are ignored instead of half-loading.
SAVE_VERSION = 3

logger = logging.getLogger(__name__)


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
    if kind == "undo":
        return Undo(seat=seat)
    if kind == "cancel_turn":
        return CancelTurn(seat=seat)
    if kind == "attack":
        return Attack(seat=seat, attacker_uid=str(payload.get("unit_uid")), target_uid=str(payload.get("target_uid")))
    if kind == "buy":
        return Buy(seat=seat, market=str(payload.get("market")), slot=int(payload.get("slot", -1)))
    if kind == "refresh":
        return Refresh(seat=seat, market=str(payload.get("market")))
    if kind == "remove_card":
        return RemoveCard(seat=seat, card_uid=str(payload.get("card_uid")))
    if kind == "develop":
        return Develop(seat=seat, unit_uid=str(payload.get("unit_uid")))
    if kind == "respond":
        return Respond(seat=seat, answer=payload.get("answer"))
    if kind == "cancel_choice":
        return CancelChoice(seat=seat)
    raise IllegalAction("error.unknown_action")


class DevGames:
    def __init__(self, catalog: Catalog, class_id: str = "mage", save_path: Path | None = None) -> None:
        self.catalog = catalog
        self.class_id = class_id
        self.save_path = save_path
        self.games: dict[str, DevGame] = {}
        self._rng = random.SystemRandom()
        # FastAPI runs sync endpoints in a thread pool, so requests can arrive in parallel.
        # One lock serialises all access: without it two fast actions could both start from
        # the same state and one of them would be silently lost.
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load saved dev games. Any problem (e.g. engine classes changed) just starts fresh."""
        if not self.save_path or not self.save_path.exists():
            return
        try:
            with self.save_path.open("rb") as fh:
                saved = pickle.load(fh)  # local dev file written by this process only
            if isinstance(saved, dict) and saved.get("version") == SAVE_VERSION:
                self.games = saved["games"]
            else:
                logger.info("Saved dev games are from an older version; starting fresh")
        except Exception:  # noqa: BLE001
            logger.warning("Couldn't load saved dev games from %s; starting fresh", self.save_path)

    def _save(self) -> None:
        if not self.save_path:
            return
        tmp = self.save_path.with_suffix(".tmp")
        with tmp.open("wb") as fh:
            pickle.dump({"version": SAVE_VERSION, "games": self.games}, fh)
        tmp.replace(self.save_path)

    def create(self, players: int, seed: int | None = None) -> str:
        with self._lock:
            return self._create(players, seed)

    def _create(self, players: int, seed: int | None) -> str:
        seed = seed if seed is not None else self._rng.randrange(2**31)
        seats = [(f"Player {i + 1}", self.class_id) for i in range(players)]
        state, events = new_game(self.catalog, seats, seed)
        game_id = generate_code(random.Random(seed), self.games)
        game = DevGame(state)
        game.record(events)
        self.games[game_id] = game
        self._save()
        return game_id

    def _get(self, game_id: str) -> DevGame:
        try:
            return self.games[game_id.upper()]
        except KeyError:
            raise GameNotFound(game_id) from None

    def view(self, game_id: str, seat: int) -> dict[str, Any]:
        with self._lock:
            return self._view(game_id, seat)

    def _view(self, game_id: str, seat: int) -> dict[str, Any]:
        game = self._get(game_id)
        view = build_view(game.state, self.catalog, seat)
        view["game_id"] = game_id.upper()
        view["log"] = list(game.log)
        return view

    def act(self, game_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._act(game_id, payload)

    def _act(self, game_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        game = self._get(game_id)
        try:
            action = parse_action(payload)
            game.state, events = apply_action(game.state, self.catalog, action)
        except IllegalAction as exc:
            return {"ok": False, "error": {"key": exc.key, "params": exc.params}}
        game.record(events)
        self._save()
        return {"ok": True, "events": [e.to_dict() for e in events]}
