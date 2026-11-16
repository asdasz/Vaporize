"""FastAPI app: serves the client and the (temporary) dev game API.

Run from the repository root:  uvicorn server.app:app --reload --reload-dir engine --reload-dir server --reload-dir data
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from engine.loader import load_catalog
from server.dev_service import DevGames, GameNotFound
from server.protocol import ActionRequest, CreateGameRequest

ROOT = Path(__file__).resolve().parent.parent

catalog = load_catalog(ROOT / "data")
games = DevGames(catalog, save_path=ROOT / ".devgames.pkl")  # survives --reload restarts
app = FastAPI(title="Vaporize")


@app.post("/api/dev/games", response_model=None)
def create_game(req: CreateGameRequest) -> dict[str, Any]:
    try:
        return {"game_id": games.create(req.players, req.seed)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/dev/games/{game_id}/view", response_model=None)
def get_view(game_id: str, seat: int) -> dict[str, Any]:
    try:
        return games.view(game_id, seat)
    except GameNotFound as exc:
        raise HTTPException(status_code=404, detail="game_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/dev/games/{game_id}/actions", response_model=None)
def post_action(game_id: str, req: ActionRequest) -> dict[str, Any]:
    try:
        return games.act(game_id, req.model_dump())
    except GameNotFound as exc:
        raise HTTPException(status_code=404, detail="game_not_found") from exc


app.mount("/locales", StaticFiles(directory=ROOT / "data" / "locales"), name="locales")
app.mount("/", StaticFiles(directory=ROOT / "client", html=True), name="client")
