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
    Bank,
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
from server.stats import MarketRecorder

LOG_LIMIT = 60
# Bump when engine state classes change, so old save files are ignored instead of half-loading.
SAVE_VERSION = 12

logger = logging.getLogger(__name__)


class GameNotFound(Exception):
    pass


@dataclass
class DevGame:
    state: GameState
    log: list[dict[str, Any]] = field(default_factory=list)
    version: int = 0  # bumped after every successful action; clients poll it to know when to reload
    record_id: str = ""  # id of this game in the statistics database (server/stats.py)
    mode: str = "dev"  # dev (hot-seat, any seat) | online (lobby room: each player only sees their own seat)

    def record(self, events: list[Event]) -> None:
        self.log.extend(e.to_dict() for e in events)
        del self.log[:-LOG_LIMIT]


def parse_action(payload: dict[str, Any]) -> Action:
    kind = payload.get("type")
    seat = int(payload.get("seat", -1))
    if kind == "play_card":
        swap = payload.get("swap")
        if swap is not None:
            if not isinstance(swap, dict) or not {"from", "to"} <= swap.keys():
                raise IllegalAction("error.swap_invalid")
            swap = (str(swap["from"]), str(swap["to"]))
        return PlayCard(seat=seat, card_uid=str(payload.get("card_uid")), swap=swap)
    if kind == "end_turn":
        return EndTurn(seat=seat, hand_discards=tuple(str(u) for u in payload.get("hand_discards") or ()))
    if kind == "undo":
        return Undo(seat=seat)
    if kind == "cancel_turn":
        return CancelTurn(seat=seat)
    if kind == "attack":
        return Attack(seat=seat, attacker_uid=str(payload.get("unit_uid")), target_uid=str(payload.get("target_uid")))
    if kind == "buy":
        return Buy(seat=seat, market=str(payload.get("market")), slot=int(payload.get("slot", -1)), pay=str(payload.get("pay") or "inf"))
    if kind == "refresh":
        return Refresh(seat=seat, market=str(payload.get("market")))
    if kind == "remove_card":
        return RemoveCard(seat=seat, card_uid=str(payload.get("card_uid")))
    if kind == "develop":
        return Develop(seat=seat, unit_uid=str(payload.get("unit_uid")), pay=str(payload.get("pay") or "inf"))
    if kind == "bank":
        return Bank(seat=seat, unit_uid=str(payload.get("unit_uid")), amount=int(payload.get("amount") or 0))
    if kind == "respond":
        return Respond(seat=seat, answer=payload.get("answer"))
    if kind == "cancel_choice":
        return CancelChoice(seat=seat)
    raise IllegalAction("error.unknown_action")


class DevGames:
    def __init__(
        self, catalog: Catalog, class_id: str = "mage", save_path: Path | None = None, recorder: MarketRecorder | None = None
    ) -> None:
        self.recorder = recorder or MarketRecorder(catalog, None)  # default: no statistics
        self.catalog = catalog
        self.class_id = class_id
        self.save_path = save_path
        self.games: dict[str, DevGame] = {}
        self.rooms: dict[str, Any] = {}  # online lobby rooms (server/rooms.py), saved together with the games
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
                self.rooms = saved.get("rooms", {})
            else:
                logger.info("Saved dev games are from an older version; starting fresh")
        except Exception:  # noqa: BLE001
            logger.warning("Couldn't load saved dev games from %s; starting fresh", self.save_path)

    def _save(self) -> None:
        if not self.save_path:
            return
        tmp = self.save_path.with_suffix(".tmp")
        with tmp.open("wb") as fh:
            pickle.dump({"version": SAVE_VERSION, "games": self.games, "rooms": self.rooms}, fh)
        tmp.replace(self.save_path)

    def create(self, players: int, seed: int | None = None, classes: list[str] | None = None) -> str:
        with self._lock:
            return self._create(players, seed, classes)

    def class_ids(self) -> list[str]:
        return sorted(self.catalog.classes)

    def taken_codes(self) -> set[str]:
        return set(self.games) | set(self.rooms)

    def _create(
        self,
        players: int,
        seed: int | None,
        classes: list[str] | None = None,
        names: list[str] | None = None,
        mode: str = "dev",
        game_id: str | None = None,
    ) -> str:
        seed = seed if seed is not None else self._rng.randrange(2**31)
        classes = classes or [self.class_id] * players
        if len(classes) != players or any(c not in self.catalog.classes for c in classes):
            raise ValueError("classes must name one known class per seat")
        names = names or [f"Player {i + 1}" for i in range(players)]
        seats = [(names[i], classes[i]) for i in range(players)]
        state, events = new_game(self.catalog, seats, seed)
        game_id = game_id or generate_code(random.Random(seed), self.taken_codes())
        game = DevGame(state, record_id=self.recorder.new_record_id(), mode=mode)
        game.record(events)
        self.games[game_id] = game
        self.recorder.game_created(game.record_id, game_id, state, mode)
        self._save()
        return game_id

    def _get(self, game_id: str, internal: bool = False) -> DevGame:
        """`internal`: called by the rooms service. The dev endpoints can't reach online games (no peeking at seats)."""
        game = self.games.get(game_id.upper())
        if game is None or (game.mode == "online" and not internal):
            raise GameNotFound(game_id)
        return game

    def view(self, game_id: str, seat: int, internal: bool = False) -> dict[str, Any]:
        with self._lock:
            return self._view(game_id, seat, internal)

    def _view(self, game_id: str, seat: int, internal: bool = False) -> dict[str, Any]:
        game = self._get(game_id, internal)
        view = build_view(game.state, self.catalog, seat)
        view["game_id"] = game_id.upper()
        view["log"] = list(game.log)
        view["version"] = game.version
        return view

    def version(self, game_id: str, internal: bool = False) -> int:
        """Cheap change marker: other windows poll this and reload their view when it changes."""
        with self._lock:
            return self._get(game_id, internal).version

    def act(self, game_id: str, payload: dict[str, Any], internal: bool = False) -> dict[str, Any]:
        with self._lock:
            return self._act(game_id, payload, internal)

    def _act(self, game_id: str, payload: dict[str, Any], internal: bool = False) -> dict[str, Any]:
        game = self._get(game_id, internal)
        try:
            action = parse_action(payload)
            before = game.state
            game.state, events = apply_action(game.state, self.catalog, action)
        except IllegalAction as exc:
            return {"ok": False, "error": {"key": exc.key, "params": exc.params}}
        if game.record_id:
            self.recorder.action_applied(game.record_id, type(action).__name__, before, game.state, events)
        game.record(events)
        game.version += 1
        self._save()
        return {"ok": True, "events": [e.to_dict() for e in events]}
