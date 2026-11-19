"""Market statistics recorder (server/stats.py) with a local SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from server.dev_service import DevGames
from server.stats import MarketRecorder, SqliteStore, TursoStore, Writer
from tests.helpers import catalog, set_hand


def _service(tmp_path: Path) -> tuple[DevGames, Path]:
    db = tmp_path / "stats.db"
    return DevGames(catalog(), recorder=MarketRecorder(catalog(), Writer(SqliteStore(db), background=False))), db


def _rows(db: Path, sql: str = "SELECT event, market, slot, modifier, price, buyer_seat, reason FROM market_events") -> list[tuple[Any, ...]]:
    with sqlite3.connect(db) as conn:
        return conn.execute(sql).fetchall()


def test_game_and_starting_market_are_recorded(tmp_path: Path) -> None:
    games, db = _service(tmp_path)
    games.create(players=2, seed=3, classes=["mage", "monarch"])
    (players, classes, mode), = _rows(db, "SELECT players, classes, mode FROM games")
    assert (players, json.loads(classes), mode) == (2, ["mage", "monarch"], "dev")
    revealed = _rows(db, "SELECT market, market_owner, market_owner_class, reason FROM market_events WHERE event = 'revealed'")
    assert sum(1 for r in revealed if r[0] == "shared") == 6
    assert {(r[1], r[2]) for r in revealed if r[0] == "private"} == {(0, "mage"), (1, "monarch")}
    assert {r[3] for r in revealed} == {"setup"}


def test_buy_records_slot_modifier_and_price(tmp_path: Path) -> None:
    games, db = _service(tmp_path)
    gid = games.create(players=2, seed=3)
    state = games.games[gid].state
    seat = state.current
    state.players[seat].inf = 30
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "shared", "slot": 0})["ok"]
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "shared", "slot": 5})["ok"]
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "shared", "slot": 2})["ok"]
    bought = _rows(db, "SELECT slot, modifier, price, buyer_seat, buyer_class, card_id FROM market_events WHERE event = 'bought'")
    assert [(r[0], r[1]) for r in bought] == [(0, 1), (5, -1), (2, 0)]
    for slot, modifier, price, buyer, cls, card_id in bought:
        assert price == max(0, catalog().card(card_id).cost + modifier)
        assert (buyer, cls) == (seat, "mage")
    refills = _rows(db, "SELECT slot FROM market_events WHERE event = 'revealed' AND reason = 'refill'")
    assert [r[0] for r in refills] == [0, 5, 2]


def test_private_buy_and_refresh_leave(tmp_path: Path) -> None:
    games, db = _service(tmp_path)
    gid = games.create(players=2, seed=3)
    state = games.games[gid].state
    seat = state.current
    state.players[seat].inf = 30
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "private", "slot": 1})["ok"]
    assert games.act(gid, {"type": "refresh", "seat": seat, "market": "shared"})["ok"]
    (market, owner, modifier), = _rows(db, "SELECT market, market_owner, modifier FROM market_events WHERE event = 'bought'")
    assert (market, owner, modifier) == ("private", seat, None)
    (slot, reason), = _rows(db, "SELECT slot, reason FROM market_events WHERE event = 'left'")
    assert (slot, reason) == (5, "refresh")


def test_basic_supply_is_not_recorded(tmp_path: Path) -> None:
    games, db = _service(tmp_path)
    gid = games.create(players=2, seed=3)
    state = games.games[gid].state
    state.players[state.current].inf = 5
    before = len(_rows(db))
    assert games.act(gid, {"type": "buy", "seat": state.current, "market": "basic", "slot": 0})["ok"]
    games.act(gid, {"type": "end_turn", "seat": state.current})
    assert len(_rows(db)) == before


def test_undone_actions_are_not_written(tmp_path: Path) -> None:
    """An undoable buy (market deck and removed pile empty: nothing revealed) that is taken back leaves no row."""
    games, db = _service(tmp_path)
    gid = games.create(players=2, seed=3)
    state = games.games[gid].state
    seat = state.current
    state.players[seat].inf = 30
    state.shared_market.deck.cards = []
    state.shared_market.removed.cards = []
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "shared", "slot": 3})["ok"]
    assert games.games[gid].state.undo_stack  # undoable: held back
    assert not _rows(db, "SELECT * FROM market_events WHERE event = 'bought'")
    assert games.act(gid, {"type": "undo", "seat": seat})["ok"]
    assert games.act(gid, {"type": "buy", "seat": seat, "market": "shared", "slot": 4})["ok"]
    assert games.act(gid, {"type": "end_turn", "seat": seat})["ok"]  # end of turn: final
    assert [r[0] for r in _rows(db, "SELECT slot FROM market_events WHERE event = 'bought'")] == [4]


def test_game_over_updates_the_game(tmp_path: Path) -> None:
    games, db = _service(tmp_path)
    gid = games.create(players=2, seed=3)
    state = games.games[gid].state
    for p in state.players:
        set_hand(state, p.seat, ["MAG-S001"] * 7)
    state.players[0].vp = 30
    for _ in range(2):
        state = games.games[gid].state
        assert games.act(gid, {"type": "end_turn", "seat": state.current})["ok"]
    (finished, winners), = _rows(db, "SELECT finished_at, winners FROM games")
    assert finished and json.loads(winners) == [0]


def test_recording_off_and_failures_never_break_a_game(tmp_path: Path) -> None:
    class Broken:
        def execute(self, statements: Any) -> None:
            raise OSError("network down")

    games = DevGames(catalog(), recorder=MarketRecorder(catalog(), Writer(Broken(), background=False)))
    gid = games.create(players=2, seed=3)
    seat = games.games[gid].state.current
    assert games.act(gid, {"type": "end_turn", "seat": seat})["ok"]
    plain = DevGames(catalog())  # default: no recorder
    assert plain.act(plain.create(players=2, seed=3), {"type": "end_turn", "seat": 0})


def test_background_writer_flushes(tmp_path: Path) -> None:
    db = tmp_path / "bg.db"
    writer = Writer(SqliteStore(db))
    games = DevGames(catalog(), recorder=MarketRecorder(catalog(), writer))
    games.create(players=3, seed=1)
    writer.flush()
    assert _rows(db, "SELECT count(*) FROM games") == [(1,)]


def test_turso_payload_shape() -> None:
    store = TursoStore("libsql://vaporize-me.turso.io", "token")
    assert store.url == "https://vaporize-me.turso.io/v2/pipeline"
    body = store.payload([("INSERT INTO t VALUES (?, ?, ?)", [1, "x", None])])
    sqls = [r.get("stmt", {}).get("sql") for r in body["requests"]]
    assert sqls == ["BEGIN", "INSERT INTO t VALUES (?, ?, ?)", "COMMIT", None]
    assert body["requests"][1]["stmt"]["args"] == [{"type": "integer", "value": "1"}, {"type": "text", "value": "x"}, {"type": "null"}]
