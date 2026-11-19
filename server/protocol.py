"""Request / response schemas for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    players: int = Field(ge=2, le=4)
    seed: Optional[int] = None
    classes: Optional[list[str]] = None  # class id per seat (default: everyone plays the Mage)


class ActionRequest(BaseModel):
    type: Literal["play_card", "end_turn", "undo", "cancel_turn", "respond", "cancel_choice", "develop", "remove_card", "attack", "buy", "refresh", "bank"]
    seat: int = Field(ge=0, le=3)
    card_uid: Optional[str] = None
    unit_uid: Optional[str] = None  # develop, attack (attacker), bank
    target_uid: Optional[str] = None  # attack
    market: Optional[Literal["shared", "private", "basic"]] = None  # buy, refresh
    pay: Optional[Literal["inf", "vp", "resource"]] = None  # buy: vp (alternative cost); develop: resource (145)
    amount: Optional[int] = None  # bank: + put resource on the unit, - take it back
    slot: Optional[int] = None  # buy
    swap: Optional[dict[str, str]] = None  # play_card: {"from": element, "to": element}
    hand_discards: Optional[list[str]] = None  # end_turn: hand cards to discard with their EOT ability
    answer: Any = None  # respond: number, uid, {uid: damage} or null (skip)


class RoomPlayerRequest(BaseModel):
    """Host or join a room, or change your own name / class in the lobby."""

    name: Optional[str] = Field(default=None, max_length=40)
    class_id: Optional[str] = None


class RoomActionRequest(ActionRequest):
    """A game action in an online room. The seat comes from the player's token, so it's optional here."""

    seat: int = Field(default=0, ge=0, le=3)
