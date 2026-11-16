# Decisions

Rule interpretations and technical choices that aren't spelled out in `docs/RULES.md`. Confirm or overturn them here.

## Rules (to confirm)

1. **"Played this turn" and the card itself.** `played_this_turn` counts the card being played unless the condition says `other: true` (card text "other ... cards"). Cards played later never count.
2. **"In your discard pile" during a turn** counts `discard + in_play`, including the card currently resolving.
3. **Mid-turn reshuffle.** If a draw effect empties the deck mid-turn, only the `discard` pile is reshuffled. Cards played this turn (`in_play`) stay out until clean up.
4. **Units count as played cards** for the 2-card minimum and for "played this turn" conditions, even though they go to the board instead of `in_play`.
5. **Resource caps.** Passives and prepare cap at the class `limit` (Mage: 4). Card effects cap at `hard_max` (Mage: 7). A gain never lowers a value that is already above the cap.

6. **Undo and hidden information.** Undo and Cancel can't go back past an action that revealed hidden information (drawing a card, reshuffling, and later scouting or revealing market cards). That action becomes the new checkpoint.
7. **Cancel keeps start-of-turn effects.** Cancel returns to the state right after start of turn (e.g. the Mage's +3 mana stays).
8. **Other players see plays immediately.** Cards played and then undone are visible to everyone (they're in the log). If uncommitted plays should stay hidden until End turn, the server can send opponents the last committed state instead.

## Technical

1. **Engine models are stdlib dataclasses, not Pydantic.** This keeps `engine/` dependency-free and pure. Validation happens in `engine/loader.py`. Pydantic is used for HTTP/WebSocket schemas in `server/`.
2. **Temporary dev API.** `server/dev_service.py` exposes hot-seat games over plain HTTP (`/api/dev/games/...`). It will be replaced by lobby rooms + WebSockets.
3. **Locale namespaces** match file names: `ui`, `cards`, `classes`, `keywords`, `log`, `error`. A key is `<namespace>.<path>`, e.g. `ui.panel.end_turn`, `cards.MAG-S01.name`, `log.card_played`.
4. **Icons are inline SVG** (`client/js/icons.js`), so there's no external icon font or CDN.
5. **Mock starter deck.** `data/cards/mage/starter/*` are placeholders (marked `# MOCK`) until the real cards arrive. For now every mock card (units included) only gives +1 inf. Engine tests that need other effects define test-only cards with `catalog_with()` in `tests/helpers.py`.
6. **Hand order is client-side.** Reordering cards by drag and drop (move and shift, not swap) doesn't go through the server. The order is stored per game and seat in `sessionStorage`. If it ever needs to sync across devices, add a `reorder_hand` action.
7. **Playing by drag.** A card is played by dragging it up out of the hand. Clicking no longer plays, to avoid accidental plays.
