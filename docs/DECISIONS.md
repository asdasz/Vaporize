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

9. **"[invoke] for X"** succeeds when the invoke value is **at least** X (card 010: Mage spends 3 mana, +1 spell bonus = 4).
10. **Split "limited to a single row"** (card 009) means all damage goes to units on **one tier**, of any players.
11. **Heal with a cap** (card 011: "can't have more than 6 HP after this card resolves") stops healing at 6 but never lowers a unit that already has more.
12. **Prepare (Mage)**: "refresh 1 spent mana" is implemented as +1 mana up to the limit of 4.
13. **Positive effects are optional.** Damage, healing and drawing a scouted card can be skipped (`allow_skip`). Invoke can't be skipped, but you may spend 0.
14. **Scout with a short deck** looks only at the cards left. It shuffles the discard pile only if the deck is completely empty.
15. **Invoke happens once per card.** Every `{invoke: N}` on the same card reuses the value. The spell bonus applies to spells only, not units.

## Technical

1. **Engine models are stdlib dataclasses, not Pydantic.** This keeps `engine/` dependency-free and pure. Validation happens in `engine/loader.py`. Pydantic is used for HTTP/WebSocket schemas in `server/`.
2. **Temporary dev API.** `server/dev_service.py` exposes hot-seat games over plain HTTP (`/api/dev/games/...`). It will be replaced by lobby rooms + WebSockets.
3. **Locale namespaces** match file names: `ui`, `cards`, `classes`, `keywords`, `log`, `error`, `prompt`. A key is `<namespace>.<path>`, e.g. `ui.panel.end_turn`, `cards.MAG-S01.name`, `log.card_played`, `prompt.invoke`.
4. **Icons are inline SVG** (`client/js/icons.js`), so there's no external icon font or CDN.
5. **Test-only cards.** Engine tests that need special effects define cards with `catalog_with()` in `tests/helpers.py` instead of depending on real card data.
6. **Hand order is client-side.** Reordering cards by drag and drop (move and shift, not swap) doesn't go through the server. The order is stored per game and seat in `sessionStorage`. If it ever needs to sync across devices, add a `reorder_hand` action.
7. **Playing by drag.** A card is played by dragging it up out of the hand. Clicking no longer plays, to avoid accidental plays.
8. **Card names.** The card table has no names yet. Names are `MAG 009 · Spell` (number + type) until real names arrive (add a Name column).
9. **One file per printed card.** IDs are `MAG-S01` … `MAG-S12` for New card # 001–012. The printed number is the `number:` field.
