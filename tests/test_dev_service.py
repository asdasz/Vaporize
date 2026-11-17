from __future__ import annotations

import threading
from pathlib import Path

from server.codes import ALPHABET
from server.dev_service import DevGames
from tests.helpers import catalog, set_hand


def _influence_hand(games: DevGames, gid: str) -> int:
    """Give the current player 7 plain influence cards (no choices needed). Returns their seat."""
    state = games.games[gid].state
    set_hand(state, state.current, ["MAG-S001"] * 7)
    return state.current


def test_create_view_and_play() -> None:
    games = DevGames(catalog())
    gid = games.create(players=3, seed=7)
    assert len(gid) == 6 and all(ch in ALPHABET for ch in gid)
    seat = _influence_hand(games, gid)
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


def test_undo_and_cancel_via_service() -> None:
    games = DevGames(catalog())
    gid = games.create(players=2, seed=2)
    seat = _influence_hand(games, gid)
    playable = games.view(gid, seat)["legal"]["playable"]
    games.act(gid, {"type": "play_card", "seat": seat, "card_uid": playable[0]})
    games.act(gid, {"type": "play_card", "seat": seat, "card_uid": playable[1]})
    assert games.act(gid, {"type": "undo", "seat": seat})["ok"]
    assert games.view(gid, seat)["legal"]["undo_count"] == 1
    assert games.act(gid, {"type": "cancel_turn", "seat": seat})["ok"]
    assert games.view(gid, seat)["legal"]["undo_count"] == 0
    assert not games.act(gid, {"type": "cancel_turn", "seat": seat})["ok"]


def test_games_survive_restart_when_saved(tmp_path: Path) -> None:
    path = tmp_path / "games.pkl"
    games = DevGames(catalog(), save_path=path)
    gid = games.create(players=2, seed=4)
    seat = games.view(gid, 0)["current"]
    games.act(gid, {"type": "end_turn", "seat": seat})
    restarted = DevGames(catalog(), save_path=path)
    assert restarted.view(gid, 0)["current"] == (seat + 1) % 2


def test_broken_save_file_starts_fresh(tmp_path: Path) -> None:
    path = tmp_path / "games.pkl"
    path.write_bytes(b"not a pickle")
    assert DevGames(catalog(), save_path=path).games == {}


def test_parallel_actions_are_not_lost() -> None:
    games = DevGames(catalog())
    gid = games.create(players=2, seed=5)
    seat = _influence_hand(games, gid)
    hand = [c["uid"] for c in games.view(gid, seat)["players"][seat]["hand"]]
    results: list[bool] = []

    def play(uid: str) -> None:
        results.append(games.act(gid, {"type": "play_card", "seat": seat, "card_uid": uid})["ok"])

    threads = [threading.Thread(target=play, args=(uid,)) for uid in hand]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    view = games.view(gid, seat)
    assert results.count(True) == 5  # 7 cards, keep 2
    assert view["players"][seat]["hand_count"] == 2
    assert view["legal"]["undo_count"] == 5


def test_old_save_format_is_ignored(tmp_path: Path) -> None:
    import pickle

    path = tmp_path / "games.pkl"
    path.write_bytes(pickle.dumps({"ABCDEF": "old game"}))
    assert DevGames(catalog(), save_path=path).games == {}
