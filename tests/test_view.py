from __future__ import annotations

import json

from engine.view import build_view
from tests.helpers import catalog, make_game


def test_view_hides_other_hands_and_deck_contents() -> None:
    state = make_game(players=3)
    view = build_view(state, catalog(), 1)
    for p in view["players"]:
        if p["seat"] == 1:
            assert len(p["hand"]) == 7
        else:
            assert p["hand"] is None
        assert p["hand_count"] == 7
        assert "deck" not in p and p["deck_count"] == 5
    json.dumps(view)  # must be JSON serialisable


def test_view_shared_market_prices_and_tier4_size() -> None:
    view = build_view(make_game(players=4), catalog(), 0)
    assert len(view["shared_market"]["row"]) == 6
    assert len(view["tier4"]) == 3


def test_legal_moves_only_for_current_player() -> None:
    state = make_game()
    current, other = state.current, (state.current + 1) % 2
    assert build_view(state, catalog(), current)["legal"]["plays_left"] == 5
    assert build_view(state, catalog(), other)["legal"]["playable"] == []
