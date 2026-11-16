"""HTTP smoke test. Skipped when FastAPI isn't installed."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402


def test_http_flow() -> None:
    client = TestClient(app)
    gid = client.post("/api/dev/games", json={"players": 2, "seed": 3}).json()["game_id"]
    view = client.get(f"/api/dev/games/{gid}/view", params={"seat": 0}).json()
    seat = view["current"]
    res = client.post(f"/api/dev/games/{gid}/actions", json={"type": "end_turn", "seat": seat}).json()
    assert res["ok"]
    assert client.get("/").status_code == 200
    assert client.get("/locales/en/ui.json").status_code == 200
    assert client.post("/api/dev/games", json={"players": 5}).status_code == 422
