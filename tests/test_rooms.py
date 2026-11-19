"""Online lobby rooms (server/rooms.py): host, join, start, play your own seat only."""

from __future__ import annotations

import pytest

from server.dev_service import DevGames, GameNotFound
from server.rooms import RoomError, Rooms
from tests.helpers import catalog


def _rooms() -> Rooms:
    return Rooms(DevGames(catalog()))


def _error(fn, *args) -> RoomError:  # type: ignore[no-untyped-def]
    with pytest.raises(RoomError) as info:
        fn(*args)
    return info.value


def test_host_join_and_lobby_view() -> None:
    rooms = _rooms()
    host = rooms.create("Jan", "monarch")
    guest = rooms.join(host["code"].lower(), "  Kasia  ", None)  # codes are case-insensitive
    view = rooms.view(host["code"], guest["token"])
    assert view["status"] == "lobby" and view["you"] == 1 and not view["host"]
    assert [(p["name"], p["class_id"], p["host"]) for p in view["players"]] == [("Jan", "monarch", True), ("Kasia", "mage", False)]
    assert rooms.view(host["code"], host["token"])["host"]


def test_fifth_player_is_told_the_room_is_full() -> None:
    rooms = _rooms()
    code = rooms.create("A", None)["code"]
    for name in "BCD":
        rooms.join(code, name, None)
    err = _error(rooms.join, code, "E", None)
    assert (err.key, err.status) == ("error.room_full", 409)


def test_unknown_room_and_token() -> None:
    rooms = _rooms()
    assert _error(rooms.join, "NOPE22", "X", None).key == "error.room_not_found"
    code = rooms.create("A", None)["code"]
    assert _error(rooms.view, code, "not-a-token").key == "error.not_in_room"
    assert _error(rooms.view, code, None).status == 403


def test_only_the_host_starts_and_needs_two_players() -> None:
    rooms = _rooms()
    host = rooms.create("A", "mage")
    code = host["code"]
    assert _error(rooms.start, code, host["token"]).key == "error.not_enough_players"
    guest = rooms.join(code, "B", "monarch")
    assert _error(rooms.start, code, guest["token"]).key == "error.not_host"
    view = rooms.start(code, host["token"])
    assert view["status"] == "playing"
    assert _error(rooms.join, code, "C", None).key == "error.room_started"
    game = rooms.game_view(code, guest["token"])
    assert game["you"] == 1 and game["online"]
    assert [(p["name"], p["class_id"]) for p in game["players"]] == [("A", "mage"), ("B", "monarch")]
    assert game["players"][0]["hand"] is None  # you never see someone else's hand


def test_players_act_only_for_their_own_seat() -> None:
    rooms = _rooms()
    host = rooms.create("A", None)
    guest = rooms.join(host["code"], "B", None)
    rooms.start(host["code"], host["token"])
    current = rooms.game_view(host["code"], host["token"])["current"]
    mine, other = (host, guest) if current == 0 else (guest, host)
    # The other player can't end my turn, even by sending my seat number.
    res = rooms.act(host["code"], other["token"], {"type": "end_turn", "seat": current})
    assert res == {"ok": False, "error": {"key": "error.not_your_turn", "params": {}}}
    before = rooms.version(host["code"], mine["token"])["version"]
    assert rooms.act(host["code"], mine["token"], {"type": "end_turn"})["ok"]
    assert rooms.version(host["code"], other["token"])["version"] != before


def test_online_games_are_hidden_from_the_dev_endpoints() -> None:
    rooms = _rooms()
    host = rooms.create("A", None)
    rooms.join(host["code"], "B", None)
    rooms.start(host["code"], host["token"])
    with pytest.raises(GameNotFound):
        rooms.games.view(host["code"], 1)  # no peeking at another seat
    with pytest.raises(GameNotFound):
        rooms.games.act(host["code"], {"type": "end_turn", "seat": 0})


def test_change_class_and_leave() -> None:
    rooms = _rooms()
    host = rooms.create("A", "mage")
    guest = rooms.join(host["code"], "B", "mage")
    view = rooms.update(host["code"], guest["token"], class_id="monarch")
    assert view["players"][1]["class_id"] == "monarch"
    assert _error(rooms.update, host["code"], guest["token"], None, "wizard").key == "error.unknown_class"
    rooms.leave(host["code"], guest["token"])
    assert len(rooms.view(host["code"], host["token"])["players"]) == 1
    rooms.leave(host["code"], host["token"])  # the host leaving closes the room
    assert _error(rooms.view, host["code"], host["token"]).key == "error.room_not_found"


def test_rooms_survive_a_restart(tmp_path) -> None:  # type: ignore[no-untyped-def]
    games = DevGames(catalog(), save_path=tmp_path / "save.pkl")
    host = Rooms(games).create("A", None)
    again = Rooms(DevGames(catalog(), save_path=tmp_path / "save.pkl"))
    assert again.view(host["code"], host["token"])["players"][0]["name"] == "A"
