"""Game state. Mutated only inside engine functions; `apply_action` works on a copy."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine.cards import CardInstance
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
    free_refresh_used: bool = False
    element_swap_used: bool = False


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

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current]

    def new_uid(self) -> str:
        self.uid_counter += 1
        return f"c{self.uid_counter}"

    def units_of(self, seat: int) -> list[tuple[int, CardInstance]]:
        """All units owned by `seat` as (tier, unit). Tokens report tier 1."""
        player = self.players[seat]
        units = [(tier, card) for tier, row in sorted(player.tiers.items()) for card in row.cards()]
        units += [(1, card) for card in player.tokens]
        units += [(4, card) for card in self.tier4.cards() if card.owner == seat]
        return units
