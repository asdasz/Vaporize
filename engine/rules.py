"""Rulebook constants. Class data may override tier/resource values."""

from __future__ import annotations

HAND_SIZE = 7
MIN_HAND = 2
STARTING_HAND = 7
VP_GOAL = 30
MIN_PLAYERS = 2
MAX_PLAYERS = 4

SHARED_MARKET_SIZE = 6
PRIVATE_MARKET_SIZE = 3
# Price modifier per shared-market slot, index 0 = leftmost.
SHARED_PRICE_MODIFIERS = (1, 0, 0, 0, 0, -1)

ELEMENTS = ("fire", "water", "wind", "lightning", "shadow")
CARD_TYPES = ("influence", "spell", "unit")
SOURCES = ("starter", "private", "shared", "basic")  # basic = always-available supply pile
STATUSES = ("shield", "stun", "freeze")
UNIT_TRIGGERS = ("sot", "eot", "on_damage_taken", "on_kill", "on_card_played")
CLASS_TRIGGERS = ("sot", "eot")

# Every keyword needs an entry in data/locales/<lang>/keywords.json.
KEYWORDS = (
    "all",
    "degrade",
    "develop",
    "disrupt",
    "eot",
    "freeze",
    "invoke",
    "on_damage_taken",
    "on_kill",
    "prepare",
    "refresh",
    "scout",
    "shield",
    "split",
    "sot",
    "stun",
    "summon",
)
