"""Request / response schemas for the HTTP API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    players: int = Field(ge=2, le=4)
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    type: Literal["play_card", "end_turn"]
    seat: int = Field(ge=0, le=3)
    card_uid: Optional[str] = None
