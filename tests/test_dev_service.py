from __future__ import annotations

from server.codes import ALPHABET
from server.dev_service import DevGames
from tests.helpers import catalog


def test_create_view_and_play() -> None:
    games = DevGames(catalog())
    gid = games.create(players=3, seed=7)
    assert len(gid) == 6 and all(ch in ALPHABET for ch in gid)
    view = games.view(gid, 0)
    seat = view["current"]
    view = games.view(gid, seat)
    uid = view["legal"]["playable"][0]
    res = games.act(gid, {"type": "play_card", "seat": seat, "card_uid": uid})
    assert res["ok"]
    assert games.act(gid, {"type": "end_turn", "seat": seat})["ok"]
    assert games.view(gid, 0)["current"] == (seat + 1) % 3


def test_illegal_action_returns_error_key() -> None:
    games = DevGames(catalog())
    gid = games.create(players=2, seed=1)
    current = games.view(gid, 0)["current"]
    res = games.act(gid, {"type": "end_turn", "seat": (current + 1) % 2})
    assert res == {"ok": False, "error": {"key": "error.not_your_turn", "params": {}}}
