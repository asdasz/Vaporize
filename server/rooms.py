"""Online lobby rooms: host a game, share the link, others join, the host starts with 2-4 players.

Each player gets a private token when they host or join. The token decides their seat: they only see their own
hand and can only act for their own seat. Rooms are saved together with the dev games (server/dev_service.py).
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from typing import Any

from engine.rules import MAX_PLAYERS, MIN_PLAYERS
from server.codes import generate_code
from server.dev_service import DevGames

NAME_MAX = 20


class RoomError(Exception):
    """An illegal lobby request. `key` is an error translation key, `status` the HTTP status to answer with."""

    def __init__(self, key: str, status: int = 400) -> None:
        super().__init__(key)
        self.key = key
        self.status = status


@dataclass
class Member:
    token: str
    name: str
    class_id: str


@dataclass
class Room:
    code: str
    host: str  # host's token
    members: list[Member] = field(default_factory=list)  # in join order = seat order
    status: str = "lobby"  # lobby | playing
    version: int = 0  # bumped on every lobby change; clients poll it


class Rooms:
    def __init__(self, games: DevGames) -> None:
        self.games = games
        self._rng = random.SystemRandom()

    @property
    def rooms(self) -> dict[str, Room]:
        return self.games.rooms

    # --- helpers --------------------------------------------------------------------------------

    def _room(self, code: str) -> Room:
        room = self.rooms.get(code.strip().upper())
        if room is None:
            raise RoomError("error.room_not_found", 404)
        return room

    def _member(self, room: Room, token: str | None) -> tuple[int, Member]:
        for seat, member in enumerate(room.members):
            if token and secrets.compare_digest(member.token, token):
                return seat, member
        raise RoomError("error.not_in_room", 403)

    def _clean_name(self, name: str | None, seat: int) -> str:
        name = " ".join((name or "").split())[:NAME_MAX]
        return name or f"Player {seat + 1}"

    def _clean_class(self, class_id: str | None) -> str:
        classes = sorted(self.games.catalog.classes)
        if class_id is None:
            return classes[0]
        if class_id not in self.games.catalog.classes:
            raise RoomError("error.unknown_class")
        return class_id

    def _changed(self, room: Room) -> None:
        room.version += 1
        self.games._save()

    # --- lobby ----------------------------------------------------------------------------------

    def create(self, name: str | None, class_id: str | None) -> dict[str, str]:
        with self.games._lock:
            code = generate_code(self._rng, self.games.taken_codes())
            token = secrets.token_urlsafe(24)
            room = Room(code=code, host=token, members=[Member(token, self._clean_name(name, 0), self._clean_class(class_id))])
            self.rooms[code] = room
            self._changed(room)
            return {"code": code, "token": token}

    def join(self, code: str, name: str | None, class_id: str | None) -> dict[str, str]:
        with self.games._lock:
            room = self._room(code)
            if room.status != "lobby":
                raise RoomError("error.room_started", 409)
            if len(room.members) >= MAX_PLAYERS:
                raise RoomError("error.room_full", 409)
            token = secrets.token_urlsafe(24)
            seat = len(room.members)
            room.members.append(Member(token, self._clean_name(name, seat), self._clean_class(class_id)))
            self._changed(room)
            return {"code": room.code, "token": token}

    def update(self, code: str, token: str | None, name: str | None = None, class_id: str | None = None) -> dict[str, Any]:
        """Change your own name or class while the room is still in the lobby."""
        with self.games._lock:
            room = self._room(code)
            seat, member = self._member(room, token)
            if room.status != "lobby":
                raise RoomError("error.room_started", 409)
            if name is not None:
                member.name = self._clean_name(name, seat)
            if class_id is not None:
                member.class_id = self._clean_class(class_id)
            self._changed(room)
            return self._view(room, token)

    def leave(self, code: str, token: str | None) -> None:
        """Leave the lobby. If the host leaves, the room closes for everyone."""
        with self.games._lock:
            room = self._room(code)
            seat, member = self._member(room, token)
            if room.status != "lobby":
                raise RoomError("error.room_started", 409)
            if member.token == room.host:
                del self.rooms[room.code]
                self.games._save()
                return
            room.members.pop(seat)
            self._changed(room)

    def start(self, code: str, token: str | None) -> dict[str, Any]:
        with self.games._lock:
            room = self._room(code)
            _, member = self._member(room, token)
            if member.token != room.host:
                raise RoomError("error.not_host", 403)
            if room.status != "lobby":
                raise RoomError("error.room_started", 409)
            if len(room.members) < MIN_PLAYERS:
                raise RoomError("error.not_enough_players")
            self.games._create(
                len(room.members), None,
                classes=[m.class_id for m in room.members], names=[m.name for m in room.members],
                mode="online", game_id=room.code,
            )
            room.status = "playing"
            self._changed(room)
            return self._view(room, token)

    def view(self, code: str, token: str | None) -> dict[str, Any]:
        with self.games._lock:
            return self._view(self._room(code), token)

    def _view(self, room: Room, token: str | None) -> dict[str, Any]:
        seat, _ = self._member(room, token)
        return {
            "code": room.code,
            "status": room.status,
            "version": self._version(room),
            "you": seat,
            "host": room.members[seat].token == room.host,  # are *you* the host
            "min_players": MIN_PLAYERS,
            "max_players": MAX_PLAYERS,
            "classes": sorted(self.games.catalog.classes),
            "players": [
                {"seat": i, "name": m.name, "class_id": m.class_id, "host": m.token == room.host, "you": i == seat}
                for i, m in enumerate(room.members)
            ],
        }

    def _version(self, room: Room) -> str:
        game = self.games.games.get(room.code) if room.status == "playing" else None
        return f"{room.version}.{game.version if game else 0}"

    def version(self, code: str, token: str | None) -> dict[str, str]:
        with self.games._lock:
            room = self._room(code)
            self._member(room, token)
            return {"status": room.status, "version": self._version(room)}

    # --- playing --------------------------------------------------------------------------------

    def game_view(self, code: str, token: str | None) -> dict[str, Any]:
        with self.games._lock:
            room = self._room(code)
            seat, _ = self._member(room, token)
            if room.status != "playing":
                raise RoomError("error.room_not_started", 409)
            view = self.games.view(room.code, seat, internal=True)
            view["version"] = self._version(room)
            view["online"] = True
            return view

    def act(self, code: str, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        with self.games._lock:
            room = self._room(code)
            seat, _ = self._member(room, token)
            if room.status != "playing":
                raise RoomError("error.room_not_started", 409)
            return self.games.act(room.code, {**payload, "seat": seat}, internal=True)  # you can only act as yourself
