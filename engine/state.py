"""Game state. Mutated only inside engine functions; `apply_action` works on a copy."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from engine.cards import CardInstance
from engine.prompts import PendingChoice
from engine.zones import SlotRow, Zone


@dataclass
class MarketState:
    deck: Zone
    row: SlotRow
    removed: Zone


@dataclass
class PlayedCard:
    """A card played this turn, in play order (units included)."""

    uid: str
    def_id: str
    elements: tuple[str, ...]


@dataclass
class PlayerState:
    seat: int
    name: str
    class_id: str
    deck: Zone
    hand: Zone
    in_play: Zone  # non-unit cards played this turn; go to discard at clean up
    discard: Zone
    removed: Zone  # removed from the game by the remove action
    tokens: Zone  # summoned token units (count as tier 1, use no spot)
    private_market: MarketState
    tiers: dict[int, SlotRow]  # own tiers 1..3
    vp: int = 0
    inf: int = 0
    resource: int = 0
    removal_index: int = 0
    played_this_turn: list[PlayedCard] = field(default_factory=list)
    # Effects that last until the end of this turn, e.g. {"kind": "next_spell_invoke_bonus", ...}
    turn_modifiers: list[dict[str, Any]] = field(default_factory=list)
    # Keys of `once_per_turn` abilities that already fired this turn.
    turn_flags: list[str] = field(default_factory=list)
    free_refresh_used: bool = False
    element_swap_used: bool = False


@dataclass
class UndoEntry:
    """Snapshot of the state before one undoable action in the current turn."""

    state: GameState
    card_id: str  # card that was played (for the log)


@dataclass
class GameState:
    players: list[PlayerState]
    shared_market: MarketState
    tier4: SlotRow
    rng: random.Random
    seed: int
    current: int = 0
    first_player: int = 0
    round: int = 1
    phase: str = "actions"  # actions | game_over
    winners: list[int] = field(default_factory=list)
    uid_counter: int = 0
    # Undoable actions of the current turn, oldest first. Cleared at end of turn
    # and whenever hidden information is revealed (e.g. a card is drawn).
    undo_stack: list[UndoEntry] = field(default_factory=list)
    # A card waiting for a player's choice (see engine/prompts.py), or None.
    pending: PendingChoice | None = None

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current]

    def new_uid(self) -> str:
        self.uid_counter += 1
        return f"c{self.uid_counter}"

    def units_of(self, seat: int) -> list[tuple[int, CardInstance]]:
        """All units owned by `seat` as (tier, unit). Undeveloped tokens report tier 1."""
        player = self.players[seat]
        units = [(tier, card) for tier, row in sorted(player.tiers.items()) for card in row.cards()]
        units += [(1, card) for card in player.tokens]
        units += [(4, card) for card in self.tier4.cards() if card.owner == seat]
        return units
