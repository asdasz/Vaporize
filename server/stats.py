"""Market statistics: every card that shows up in, is bought from or leaves a market, for every game.

The engine stays pure: it only emits events (`log.market_revealed`, `log.card_bought`, …). This module turns
them into rows and writes them to a database in a background thread, so a slow network never delays a game.

Storage (see `store_from_env`):
- `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` set: Turso over its HTTP API (`/v2/pipeline`), no extra packages.
- otherwise a local SQLite file (`.stats.db` in the repository root, or `VAPORIZE_STATS_DB`).
- `VAPORIZE_STATS=off` turns recording off.

Undo: market events of undoable actions are held back until the turn reaches a checkpoint (revealed
information, end of turn), so taken-back actions are never written. Most market events reveal a new card and
are written right away.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from engine.catalog import Catalog
from engine.events import Event
from engine.rules import SHARED_PRICE_MODIFIERS
from engine.state import GameState

logger = logging.getLogger(__name__)

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS games (
        id TEXT PRIMARY KEY,
        code TEXT,
        mode TEXT,            -- dev (hot-seat) | online
        created_at TEXT,
        finished_at TEXT,
        players INTEGER,
        classes TEXT,         -- JSON list, class id per seat
        seed INTEGER,
        winners TEXT,         -- JSON list of seats
        rounds INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS market_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL,
        created_at TEXT,
        round INTEGER,
        turn_seat INTEGER,          -- whose turn it was
        market TEXT,                -- shared | private
        market_owner INTEGER,       -- private market: whose market
        market_owner_class TEXT,
        slot INTEGER,               -- shared: 0 = leftmost (+1 inf) … 5 = rightmost (-1 inf)
        card_id TEXT,
        card_number INTEGER,
        event TEXT,                 -- revealed | bought | bought_vp | left
        buyer_seat INTEGER,
        buyer_class TEXT,
        price INTEGER,              -- inf paid
        modifier INTEGER,           -- shared slot price modifier: +1 / 0 / -1
        vp_paid INTEGER,
        reason TEXT                 -- revealed: setup | refill; left: refresh | discarded | resolved
    )""",
    "CREATE INDEX IF NOT EXISTS market_events_game ON market_events (game_id)",
    "CREATE INDEX IF NOT EXISTS market_events_card ON market_events (card_id)",
)

EVENT_COLUMNS = (
    "game_id", "created_at", "round", "turn_seat", "market", "market_owner", "market_owner_class", "slot",
    "card_id", "card_number", "event", "buyer_seat", "buyer_class", "price", "modifier", "vp_paid", "reason",
)
INSERT_EVENT = f"INSERT INTO market_events ({', '.join(EVENT_COLUMNS)}) VALUES ({', '.join('?' * len(EVENT_COLUMNS))})"
TRACKED_MARKETS = ("shared", "private")  # the basic supply isn't a market row

Statement = tuple[str, list[Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- storage ------------------------------------------------------------------------------------


class Store(Protocol):
    def execute(self, statements: list[Statement]) -> None: ...


class SqliteStore:
    """Local SQLite file (development, tests)."""

    def __init__(self, path: Path | str) -> None:
        self.path = str(path)

    def execute(self, statements: list[Statement]) -> None:
        with sqlite3.connect(self.path) as conn:  # commits on success
            for sql, args in statements:
                conn.execute(sql, args)


def _turso_arg(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


class TursoStore:
    """Turso over HTTP (https://docs.turso.tech/sdk/http/reference). One pipeline request per batch, in a transaction."""

    def __init__(self, url: str, token: str, timeout: float = 10.0) -> None:
        self.url = url.replace("libsql://", "https://", 1).rstrip("/") + "/v2/pipeline"
        self.token = token
        self.timeout = timeout

    def payload(self, statements: list[Statement]) -> dict[str, Any]:
        requests = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
        requests += [{"type": "execute", "stmt": {"sql": sql, "args": [_turso_arg(a) for a in args]}} for sql, args in statements]
        requests += [{"type": "execute", "stmt": {"sql": "COMMIT"}}, {"type": "close"}]
        return {"requests": requests}

    def execute(self, statements: list[Statement]) -> None:
        body = json.dumps(self.payload(statements)).encode()
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:  # noqa: S310 (fixed https URL from config)
            result = json.loads(res.read() or b"{}")
        errors = [r.get("error") for r in result.get("results", []) if r.get("type") == "error"]
        if errors:
            raise RuntimeError(f"Turso error: {errors[0]}")


def store_from_env(root: Path) -> Store | None:
    if os.environ.get("VAPORIZE_STATS", "").lower() == "off":
        return None
    url, token = os.environ.get("TURSO_DATABASE_URL"), os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return TursoStore(url, token)
    return SqliteStore(os.environ.get("VAPORIZE_STATS_DB") or root / ".stats.db")


class Writer:
    """Runs store writes in order on a background thread (or inline with `background=False`, for tests).

    Failures are logged and dropped: statistics must never break a game.
    """

    def __init__(self, store: Store, background: bool = True) -> None:
        self.store = store
        self.background = background
        self._queue: queue.Queue[list[Statement] | None] = queue.Queue()
        self._ready = False
        if background:
            threading.Thread(target=self._run, name="stats-writer", daemon=True).start()

    def _write(self, statements: list[Statement]) -> None:
        try:
            if not self._ready:
                self.store.execute([(sql, []) for sql in SCHEMA])
                self._ready = True
            self.store.execute(statements)
        except Exception:  # noqa: BLE001
            logger.warning("Couldn't write %d statistics statement(s)", len(statements), exc_info=True)

    def _run(self) -> None:
        while True:
            batch = self._queue.get()
            if batch is None:
                return
            self._write(batch)
            self._queue.task_done()

    def submit(self, statements: list[Statement]) -> None:
        if not statements:
            return
        if self.background:
            self._queue.put(statements)
        else:
            self._write(statements)

    def flush(self) -> None:
        if self.background:
            self._queue.join()


# --- recording ----------------------------------------------------------------------------------


@dataclass
class _Game:
    record_id: str
    groups: list[list[Statement]] = field(default_factory=list)  # one per undoable action since the checkpoint


class MarketRecorder:
    """Turns engine events into `games` / `market_events` rows. Called by the game service after every action."""

    def __init__(self, catalog: Catalog, writer: Writer | None) -> None:
        self.catalog = catalog
        self.writer = writer
        self.games: dict[str, _Game] = {}

    @property
    def enabled(self) -> bool:
        return self.writer is not None

    def new_record_id(self) -> str:
        return uuid.uuid4().hex

    def game_created(self, record_id: str, code: str, state: GameState, mode: str = "dev") -> None:
        if not self.writer:
            return
        self.games[record_id] = _Game(record_id)
        classes = [p.class_id for p in state.players]
        rows: list[Statement] = [(
            "INSERT INTO games (id, code, mode, created_at, players, classes, seed) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [record_id, code, mode, _now(), len(state.players), json.dumps(classes), state.seed],
        )]
        markets = [("shared", state.shared_market, None)] + [("private", p.private_market, p.seat) for p in state.players]
        for name, market, owner in markets:  # the cards on the table when the game starts
            for slot, card in enumerate(market.row.slots):
                if card is not None:
                    rows.append(self._row(record_id, state, "revealed", name, slot, card.def_id, owner=owner, reason="setup"))
        self.writer.submit(rows)

    def action_applied(self, record_id: str, kind: str, before: GameState, after: GameState, events: list[Event]) -> None:
        """`kind` is the action's class name (PlayCard, Undo, …)."""
        if not self.writer:
            return
        game = self.games.setdefault(record_id, _Game(record_id))
        rows = self._rows(record_id, before, events)
        depth = len(after.undo_stack)
        if kind == "Undo":
            if game.groups:
                game.groups.pop()  # taken back: never written
        elif kind == "CancelTurn":
            game.groups.clear()
        elif depth == 0:  # checkpoint (revealed information) or end of turn: everything so far is final
            final = [s for group in game.groups for s in group] + rows
            game.groups.clear()
            self.writer.submit(final)
        elif depth == len(game.groups) + 1:  # a new undoable action
            game.groups.append(rows)
        elif rows:  # shouldn't happen; keep the data rather than lose it
            self.writer.submit(rows)
        if any(e.key == "log.game_over" for e in events):
            self.writer.submit([(
                "UPDATE games SET finished_at = ?, winners = ?, rounds = ? WHERE id = ?",
                [_now(), json.dumps(list(after.winners)), after.round, record_id],
            )])

    def _rows(self, record_id: str, state: GameState, events: list[Event]) -> list[Statement]:
        rows: list[Statement] = []
        for e in events:
            p = e.params
            market = p.get("market")
            if market not in TRACKED_MARKETS:
                continue
            owner = p.get("owner")
            if e.key == "log.market_revealed":
                rows.append(self._row(record_id, state, "revealed", market, p.get("slot"), p["card"], owner=owner, reason="refill"))
            elif e.key == "log.card_bought":
                rows.append(self._row(
                    record_id, state, "bought", market, p.get("slot"), p["card"], owner=owner, buyer=p["seat"],
                    price=p.get("price"), modifier=p.get("modifier"),
                ))
            elif e.key == "log.card_bought_vp":
                rows.append(self._row(record_id, state, "bought_vp", market, p.get("slot"), p["card"], owner=owner, buyer=p["seat"], vp=p.get("vp")))
            elif e.key in ("log.market_card_left", "log.market_card_discarded", "log.market_card_resolved"):
                reason = {"log.market_card_left": p.get("reason", "refresh"), "log.market_card_discarded": "discarded"}.get(e.key, "resolved")
                rows.append(self._row(record_id, state, "left", market, p.get("slot"), p["card"], owner=owner, reason=reason))
        return rows

    def _row(
        self, record_id: str, state: GameState, event: str, market: str, slot: int | None, card_id: str, *,
        owner: int | None = None, buyer: int | None = None, price: int | None = None, modifier: int | None = None,
        vp: int | None = None, reason: str | None = None,
    ) -> Statement:
        cls = lambda seat: state.players[seat].class_id if seat is not None and 0 <= seat < len(state.players) else None  # noqa: E731
        if market == "shared" and modifier is None and event in ("bought", "bought_vp") and slot is not None:
            modifier = SHARED_PRICE_MODIFIERS[slot]
        card = self.catalog.cards.get(card_id)
        values = {
            "game_id": record_id, "created_at": _now(), "round": state.round, "turn_seat": state.current,
            "market": market, "market_owner": owner, "market_owner_class": cls(owner), "slot": slot,
            "card_id": card_id, "card_number": card.number if card else None, "event": event,
            "buyer_seat": buyer, "buyer_class": cls(buyer), "price": price, "modifier": modifier, "vp_paid": vp,
            "reason": reason,
        }
        return INSERT_EVENT, [values[c] for c in EVENT_COLUMNS]
