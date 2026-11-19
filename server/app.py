"""FastAPI app: serves the client and the (temporary) dev game API.

Run from the repository root:  uvicorn server.app:app --reload --reload-dir engine --reload-dir server --reload-dir data
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from engine.loader import load_catalog
from server.dev_service import DevGames, GameNotFound
from server.stats import MarketRecorder, Writer, store_from_env
from server.protocol import ActionRequest, CreateGameRequest, RoomActionRequest, RoomPlayerRequest
from server.rooms import RoomError, Rooms

ROOT = Path(__file__).resolve().parent.parent

catalog = load_catalog(ROOT / "data")
_store = store_from_env(ROOT)  # Turso if TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are set, else .stats.db (SQLite)
recorder = MarketRecorder(catalog, Writer(_store) if _store else None)
games = DevGames(catalog, save_path=ROOT / ".devgames.pkl", recorder=recorder)  # survives --reload restarts
rooms = Rooms(games)
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


# --- online rooms: the player's token travels in the X-Player-Token header -----------------------


def _room_call(fn: Callable[..., Any], *args: Any) -> Any:
    try:
        return fn(*args)
    except RoomError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.key) from exc


Token = Header(default=None, alias="X-Player-Token")


@app.post("/api/rooms", response_model=None)
def host_room(req: RoomPlayerRequest) -> dict[str, Any]:
    return _room_call(rooms.create, req.name, req.class_id)


@app.post("/api/rooms/{code}/join", response_model=None)
def join_room(code: str, req: RoomPlayerRequest) -> dict[str, Any]:
    return _room_call(rooms.join, code, req.name, req.class_id)


@app.get("/api/rooms/{code}", response_model=None)
def room_view(code: str, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.view, code, token)


@app.post("/api/rooms/{code}/player", response_model=None)
def room_update(code: str, req: RoomPlayerRequest, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.update, code, token, req.name, req.class_id)


@app.post("/api/rooms/{code}/leave", response_model=None)
def room_leave(code: str, token: str | None = Token) -> dict[str, Any]:
    _room_call(rooms.leave, code, token)
    return {"ok": True}


@app.post("/api/rooms/{code}/start", response_model=None)
def room_start(code: str, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.start, code, token)


@app.get("/api/rooms/{code}/version", response_model=None)
def room_version(code: str, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.version, code, token)


@app.get("/api/rooms/{code}/game", response_model=None)
def room_game(code: str, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.game_view, code, token)


@app.post("/api/rooms/{code}/actions", response_model=None)
def room_action(code: str, req: RoomActionRequest, token: str | None = Token) -> dict[str, Any]:
    return _room_call(rooms.act, code, token, req.model_dump())


app.mount("/locales", StaticFiles(directory=ROOT / "data" / "locales"), name="locales")
app.mount("/", StaticFiles(directory=ROOT / "client", html=True), name="client")
