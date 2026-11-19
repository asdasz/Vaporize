"""FastAPI app: serves the client and the (temporary) dev game API.

Run from the repository root:  uvicorn server.app:app --reload --reload-dir engine --reload-dir server --reload-dir data
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from engine.loader import load_catalog
from server.dev_service import DevGames, GameNotFound
from server.stats import MarketRecorder, Writer, store_from_env
from server.protocol import ActionRequest, CreateGameRequest

ROOT = Path(__file__).resolve().parent.parent

catalog = load_catalog(ROOT / "data")
_store = store_from_env(ROOT)  # Turso if TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are set, else .stats.db (SQLite)
recorder = MarketRecorder(catalog, Writer(_store) if _store else None)
games = DevGames(catalog, save_path=ROOT / ".devgames.pkl", recorder=recorder)  # survives --reload restarts
app = FastAPI(title="Vaporize")


@app.middleware("http")
async def no_stale_files(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Make browsers revalidate client files and locales on every load, so a stale cache can't mix
    old card data (e.g. renamed card IDs) with new code."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.post("/api/dev/games", response_model=None)
def create_game(req: CreateGameRequest) -> dict[str, Any]:
    try:
        return {"game_id": games.create(req.players, req.seed, req.classes)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health", response_model=None)
def health() -> dict[str, Any]:
    """For the hosting platform's health check."""
    return {"ok": True}


@app.get("/api/dev/classes", response_model=None)
def list_classes() -> dict[str, Any]:
    return {"classes": games.class_ids()}


@app.get("/api/dev/games/{game_id}/view", response_model=None)
def get_view(game_id: str, seat: int) -> dict[str, Any]:
    try:
        return games.view(game_id, seat)
    except GameNotFound as exc:
        raise HTTPException(status_code=404, detail="game_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/dev/games/{game_id}/version", response_model=None)
def get_version(game_id: str) -> dict[str, Any]:
    try:
        return {"version": games.version(game_id)}
    except GameNotFound as exc:
        raise HTTPException(status_code=404, detail="game_not_found") from exc


@app.post("/api/dev/games/{game_id}/actions", response_model=None)
def post_action(game_id: str, req: ActionRequest) -> dict[str, Any]:
    try:
        return games.act(game_id, req.model_dump())
    except GameNotFound as exc:
        raise HTTPException(status_code=404, detail="game_not_found") from exc


app.mount("/locales", StaticFiles(directory=ROOT / "data" / "locales"), name="locales")
app.mount("/", StaticFiles(directory=ROOT / "client", html=True), name="client")
