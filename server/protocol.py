"""Request / response schemas for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    players: int = Field(ge=2, le=4)
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    type: Literal["play_card", "end_turn", "undo", "cancel_turn", "respond", "cancel_choice", "develop", "remove_card", "attack", "buy", "refresh"]
    seat: int = Field(ge=0, le=3)
    card_uid: Optional[str] = None
    unit_uid: Optional[str] = None  # develop, attack (attacker)
    target_uid: Optional[str] = None  # attack
    market: Optional[Literal["shared", "private", "basic"]] = None  # buy, refresh
    pay: Optional[Literal["inf", "vp"]] = None  # buy: pay the alternative VP cost
    slot: Optional[int] = None  # buy
    swap: Optional[dict[str, str]] = None  # play_card: {"from": element, "to": element}
    hand_discards: Optional[list[str]] = None  # end_turn: hand cards to discard with their EOT ability
    answer: Any = None  # respond: number, uid, {uid: damage} or null (skip)
