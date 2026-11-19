"""HTTP smoke test. Skipped when FastAPI isn't installed."""

from __future__ import annotations

import importlib.util
import os

import pytest

pytest.importorskip("fastapi")
if not (importlib.util.find_spec("httpx2") or importlib.util.find_spec("httpx")):
    pytest.skip("TestClient needs httpx2 (or legacy httpx)", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

os.environ["VAPORIZE_STATS"] = "off"  # don't write statistics from tests
from server.app import app  # noqa: E402


def test_http_flow() -> None:
    client = TestClient(app)
    gid = client.post("/api/dev/games", json={"players": 2, "seed": 3}).json()["game_id"]
    view = client.get(f"/api/dev/games/{gid}/view", params={"seat": 0}).json()
    seat = view["current"]
    assert client.get(f"/api/dev/games/{gid}/version").json() == {"version": 0}
    res = client.post(f"/api/dev/games/{gid}/actions", json={"type": "end_turn", "seat": seat}).json()
    assert res["ok"]
    assert client.get(f"/api/dev/games/{gid}/version").json() == {"version": 1}
    assert client.get("/api/dev/games/NOPE00/version").status_code == 404
    assert client.get("/").status_code == 200
    assert client.get("/api/health").json() == {"ok": True}
    locale = client.get("/locales/en/ui.json")
    assert locale.status_code == 200 and locale.headers["cache-control"] == "no-cache"
    assert client.post("/api/dev/games", json={"players": 5}).status_code == 422
    assert "monarch" in client.get("/api/dev/classes").json()["classes"]
    mixed = client.post("/api/dev/games", json={"players": 2, "classes": ["mage", "monarch"]}).json()["game_id"]
    assert client.get(f"/api/dev/games/{mixed}/view", params={"seat": 1}).json()["players"][1]["class_id"] == "monarch"
    assert client.post("/api/dev/games", json={"players": 2, "classes": ["mage", "nope"]}).status_code == 400
