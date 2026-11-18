# CLAUDE.md — Vaporize

Guidance for AI agents (and humans) working on this repository. Read this file first, then `docs/RULES.md`.

## Project

Vaporize is an online deck-building card game for 2–4 players. Each player leads one of five classes (Mage, Robot, …), builds a deck, develops units through tiers 1–4 and races to 30 VP. The full rulebook is in `docs/RULES.md` and is the source of truth for game rules.

**Golden rule (from the rulebook):** when a card or a character board contradicts the rulebook, the card or board wins. The engine must allow card/class data to override default rules.

## Language

- Everything is in **English** by default: code, comments, commit messages, docs, UI strings, card data.
- User-facing text is never hardcoded. It always goes through translation keys (see *Internationalisation*).
- Only `en` ships for now, but every feature must be built so that adding a language means adding one locale folder and nothing else.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.14 (code stays 3.10-compatible) | Type hints everywhere, `from __future__ import annotations` |
| Server | FastAPI + WebSockets (uvicorn) | Authoritative: all rules run on the server |
| Data models | stdlib dataclasses in `engine/`, Pydantic v2 in `server/` | Engine stays dependency-free; loader validates YAML |
| Card / class data | YAML | One file per card, human-editable |
| Client | Plain HTML + CSS + JavaScript (ES modules) | No build step, no framework, served by FastAPI as static files |
| Tests | pytest | Engine is fully testable without a server or browser |
| Hosting | Render / Railway / Fly.io (TBD) | Single process, in-memory game rooms for now |

## Architecture

```
Browser client  ──WebSocket──►  server/  ──calls──►  engine/  ──reads──►  data/
(renders view,                 (rooms, lobby,       (pure game logic,     (cards, classes,
 sends intents)                 auth-less sessions)  no I/O)               locales)
```

Principles:

1. **Engine is pure.** `engine/` has no network, file or time access. It receives a `GameState` plus an `Action` and returns a new state plus a list of `Event`s. Randomness comes from a seeded RNG stored in the state, so every game is replayable from seed + action log.
2. **Server is authoritative.** The client only sends intents (`play_card`, `buy`, `attack`, …). The server validates them through the engine. The client never decides whether something is legal.
3. **Redacted views.** The server sends each player a `PlayerView`: their own hand is visible, opponents' hands are counts only, and deck order is hidden for everyone. Private markets (face-up cards) and discard piles are public information.
4. **Data, not code, for cards.** Cards are YAML files that reference reusable effects by name. No card has its own Python logic.
5. **Choices are prompts.** When the engine needs a decision (pick a target, choose the order of simultaneous effects, split damage, choose Mage element swap), it pauses and emits a `Prompt`. The client answers with a `PromptResponse` action.

## Repository layout

```
vaporize/
├── CLAUDE.md
├── docs/
│   └── RULES.md                 # rulebook (source of truth)
├── data/
│   ├── cards/
│   │   ├── shared/              # shared-market cards (source: shared) and basic supply (source: basic)
│   │   │   └── SHR-713_primary_inf.yaml
│   │   ├── mage/
│   │   │   ├── starter/         # MAG-S001 … MAG-S012
│   │   │   └── private/         # MAG-P031 … MAG-P045 (private market)
│   │   └── robot/ …
│   ├── classes/
│   │   └── mage.yaml            # character board: tiers, resource, passives, prepare, invoke
│   └── locales/
│       └── en/
│           ├── ui.json          # UI strings
│           ├── cards.json       # card names + rules text, keyed by card ID
│           ├── classes.json     # class names, passives, prepare/invoke text
│           ├── keywords.json    # keyword names + reminder text
│           ├── log.json         # game log messages (event keys)
│           ├── error.json       # illegal-action messages
│           └── prompt.json      # questions asked while a card resolves
├── engine/
│   ├── rules.py                 # rulebook constants (hand size, elements, keywords, ...)
│   ├── state.py                 # GameState, PlayerState, MarketState
│   ├── zones.py                 # Zone (ordered pile) + helpers
│   ├── cards.py                 # CardDef (static) and CardInstance (runtime)
│   ├── catalog.py               # Catalog: all loaded CardDefs + ClassDefs
│   ├── setup.py                 # new_game(): rulebook setup
│   ├── drawing.py               # draw / draw-up-to with reshuffle
│   ├── resolver.py              # runs effect lists (if/then/else)
│   ├── context.py               # EffectContext passed to effects
│   ├── loader.py                # loads + validates YAML into CardDef / ClassDef
│   ├── actions.py               # player actions: play, respond, cancel_choice, develop, remove_card, attack, buy, refresh, undo, cancel_turn, end_turn
│   ├── playing.py               # resolving a played card (unit stats, "next spell" modifiers, on_card_played triggers)
│   ├── attacks.py               # unit attacks (range, tap, kill rewards)
│   ├── market.py                # buy / refresh, price modifiers, market reveal + reshuffle
│   ├── removal.py               # removing cards from the game (cost track)
│   ├── development.py           # develop (tier up) rules, legal develops, end-of-turn VP preview
│   ├── errors.py                # IllegalAction (translation key + params)
│   ├── invoke.py                # class invoke modes + spell bonus
│   ├── element_swap.py          # Mage passive: change one printed element when playing a card
│   ├── cardview.py              # JSON-ready card description (views, prompts)
│   ├── history.py               # undo snapshots for the current turn
│   ├── turn.py                  # SOT → actions → EOT sequencing, round + game end
│   ├── combat.py                # damage, shields, healing, destruction
│   ├── effects/
│   │   ├── registry.py          # @effect("name") decorator + lookup
│   │   ├── resources.py         # gain_inf, gain_resource, lose_resource, gain_vp, …
│   │   ├── damage.py            # deal_damage, heal, split handling
│   │   ├── keywords.py          # grant_keyword (e.g. Split)
│   │   ├── cards.py             # draw, scout, play_from_discard
│   │   ├── modifiers.py         # next_spell_invoke_bonus, next_spell_twice, boost_attack, vp_per_attack_kill
│   │   ├── class_hooks.py       # prepare (delegates to ClassDef)
│   │   ├── status.py            # shield, stun, freeze tokens
│   │   ├── movement.py          # develop (effect, e.g. free), degrade (optional refund)
│   │   ├── market_effects.py    # refresh_market (free, up to N, every market), discard_from_market
│   │   └── …                    # units.py (summon) to come
│   ├── conditions.py            # played_this_turn, in_discard, has_unit_on_tier, …
│   ├── targeting.py             # target selectors (ally/enemy/any, tier ranges)
│   ├── values.py                # value expressions: literal, invoke, invoke+N, count_of(…)
│   ├── events.py                # Event types (for log + client animations)
│   ├── prompts.py               # Prompt, NeedChoice, PendingChoice
│   └── view.py                  # GameState → PlayerView (redaction)
├── server/
│   ├── app.py                   # FastAPI app, static files, API endpoints
│   ├── dev_service.py           # temporary hot-seat dev games (HTTP)
│   ├── codes.py                 # 6-char join codes
│   ├── rooms.py                 # (planned) lobby rooms over WebSockets
│   └── protocol.py              # message schemas (client ⇄ server)
├── client/
│   ├── index.html
│   ├── css/
│   └── js/
│       ├── main.js
│       ├── net.js               # WebSocket wrapper
│       ├── i18n.js              # t(key, params)
│       ├── lobby.js             # create / join screen
│       └── board/               # one module per UI region (see UI design)
└── tests/
    ├── effects/                 # one test file per effect module
    ├── cards/                   # data validation for every card file
    └── test_turn.py, test_combat.py, …
```

## Zones (card piles)

Every pile is its own explicit `Zone` object. Never infer a pile from a flag on a card.

**Per player**

| Zone | Order matters | Visibility |
|---|---|---|
| `deck` | yes (top = index 0) | hidden (count only) |
| `hand` | no | owner only |
| `in_play` | yes (play order) | public; cards played this turn |
| `discard` | yes | public |
| `removed` | no | public; cards removed from the game via the removal action |
| `private_market.deck` | yes | hidden |
| `private_market.row` | 3 slots | public (UI hides behind a click) |
| `private_market.removed` | yes | public |

**Shared**

| Zone | Notes |
|---|---|
| `shared_market.deck` | hidden |
| `shared_market.row` | 6 fixed slots, index 0 = leftmost (+1 inf), index 5 = rightmost (−1 inf) |
| `shared_market.removed` | public; reshuffled into the deck when the deck runs out |
| `basic_supply` | face-up pile of basic cards (701–712), buyable at any time at printed price; not part of the 6-card market, never refreshed |

**Board**

- `player.tiers[1..3]`: per-player `SlotRow`s; spot counts come from the player's `ClassDef`.
- `state.tier4`: shared `SlotRow`, `players − 1` slots.
- `player.tokens`: summoned token units. They count as Tier 1 but don't use a Tier 1 spot.
- `player.played_this_turn`: ordered list of every card played this turn (units included), used by "played this turn" conditions.

Rule notes the engine must respect:

- "In your discard pile" counts `discard + in_play`. Cards played this turn are already counted as discarded for queries and for the remove action.
- "Played this turn" conditions use `player.played_this_turn`: only cards played **before** the current one, plus the card itself unless the condition has `other: true` (see `docs/DECISIONS.md`).
- When the deck is empty and a draw/scout is needed, shuffle `discard` into `deck` first.
- Destroyed units go to the owner's `discard`. Destroyed tokens are deleted.

## Developing units and scoring

- `Develop(seat, unit_uid)` moves one of your units up **one** tier (no skipping) and costs the target tier's `develop_cost` from the owner's class (Mage: T2 3, T3 4, T4 5 inf).
- It needs a free spot on the target tier. Tier 4 is the shared `state.tier4` row with `players − 1` spots, first come first served.
- A unit with a freeze token can't develop. Developing doesn't heal or untap. It's undoable like playing a card.
- Tokens can develop too: they leave `player.tokens` and take a normal spot on the next tier, but stay tokens (deleted when destroyed).
- End of turn: every unit scores its tier's `vp` (T1 0, T2 1, T3 2, T4 3), tokens included. `eot_vp()` gives the same number as a preview for the UI.
- The view lists legal develops as `legal.develop = {uid: {cost, to}}`. The UI shows a green "↑ T2 · 3" button on those units.

## Attacks

- `Attack(seat, attacker_uid, target_uid)`: an untapped own unit with attack > 0 and no stun token hits an **enemy** unit on the same tier or one tier higher. Damage = attack (`fixed_attack + temp_attack`); shields absorb the hit; the target doesn't strike back. The attacker becomes tapped and untaps at the end of its owner's turn.
- If the target is destroyed: `vp_per_attack_kill` turn modifiers pay VP and the attacker's `on_kill` trigger runs.
- A unit attacks once per turn, plus static `extra_attacks` modifiers and `temp_extra_attacks` granted this turn (`boost_units`). `attacks_made` counts; the unit is tapped when it runs out. Both reset at its owner's end of turn.
- `taunt` units (set from the modifier when they enter): enemies can't target that player's other units, by attacks or by effects, while they could target the taunting unit instead (`error.must_target_taunt`).
- Undoable. The view lists `legal.attacks = {attacker_uid: [target uids]}`. UI: click a green-outlined own unit to select it (blue), then click a red-tinted enemy to attack. Clicking anywhere else drops the selection.

## Markets

- `Buy(seat, market, slot, pay)` with `pay` = `inf` (default) or `vp` for cards with `alt_cost: {lose_vp: N}` (you need at least N VP; market price modifiers don't apply). `market` = `shared`, `private` (your own only) or `basic` (top card of the basic supply; `slot` is ignored, no price modifier, nothing is revealed so it's undoable). Price = printed cost, in the shared market +1 for the leftmost slot and −1 for the rightmost. The card goes to your discard pile (owner = you) and a new card is revealed into the same slot.
- `Refresh(seat, market)`: the rightmost card goes to the market's removed pile, the others slide right, and a new card is revealed on the left. The first shared refresh each turn is free; every other refresh costs 1 inf.
- When a market deck is empty, its removed pile is shuffled into a new deck.
- Revealing a market card is hidden information, so a buy or refresh that reveals a card becomes a new undo checkpoint.
- The view lists `legal.market = {shared_buy: [slots], private_buy: [slots], shared_refresh: cost|null, private_refresh: cost|null}`. UI: buyable cards get a green outline (click to buy). Green refresh buttons sit next to the markets.
- Each market row starts with two piles on the left: the face-down **deck** and the face-up **removed** pile. Market changes are animated (`client/js/board/animate.js`, FLIP): on refresh the cards slide right, the rightmost card flies to the removed pile and the new card comes out of the deck. A bought card flies to the buyer's panel.

## Element swap (Mage passive)

- `PlayCard(seat, card_uid, swap=(from, to))`: once per turn, for free, the played card treats one printed element as another (`player.element_swap_used`).
- Allowed only for cards with 1 or 2 printed elements. Cards with all five elements or none can't change. `to` must be a single element the card doesn't already have, so there are no duplicates and never "all".
- The swap sets `card.effective_elements`. It counts for "played this turn" and "in your discard pile" while the card is in play, and resets when played cards go to the discard pile at end of turn. "Element changes don't count" cards (e.g. 032) read printed elements.
- The swap is stored in `PendingChoice.swap`, so it survives prompts. Undo restores it.
- The view: `legal.element_swap = {has, available, options: {uid: {from: [to…]}}}`.
- UI: a green ⇄ button on swappable hand cards opens an inline panel ("Change [fire] into [water | wind | …]"). The chosen swap shows on the card (accent-coloured element icons) and is sent with the next play of that card. The chip "Element swap available" turns grey with a strikethrough once used.

## End of turn choices

- End-of-turn abilities may ask questions (e.g. 782 invokes and picks a target). `EndTurn` is then replayed like a card: `state.pending.kind == "end_turn"` (with the chosen `hand_discards`), `Respond` continues, and `CancelChoice` goes back to before ending the turn. Unit EOT triggers run **before** the class's EOT passive.
- `EndTurn(seat, hand_discards=(uid, …))`: hand cards with `hand_eot: {discard_for_vp: N}` (e.g. 731) that the player chooses to discard at the start of their end of turn, for N VP each. This may break the 2-card minimum (the card says so).
- UI: if the hand has such cards, End turn first opens a small panel with a checkbox per card.

## Removing cards

- `RemoveCard(seat, card_uid)` removes a card from the **hand**, **played this turn** (`in_play`) or the **discard pile** into `player.removed`. Cards in the deck can't be removed. Removing from the hand respects the 2-card minimum, and a card removed from the hand never counts as played.
- Cost comes from the class `removal_costs` track (1, 1, 2, 2, 3, 3, …), paid in inf; `player.removal_index` moves 1 space per removal. When the track is used up, no more removals.
- Effects of a removed played card stay: inf it gave, and its elements in `played_this_turn`.
- Undoable. The view lists `legal.removable` (uids) and each player's `removed` pile.
- UI (Hearthstone-style): a green "Remove a card: N inf" chip opens an overlay in the middle of the screen with the cards grouped as **In hand / Played this turn / Discard pile**. Removable cards are outlined green and turn red on hover. "Peek at the table" hides the overlay until "Back to removing a card". Picking any card asks for confirmation first (the hand version adds that the card won't be played). Esc, Cancel or a click outside closes it.

## Undo

- Every undoable action pushes a snapshot of the state before it onto `state.undo_stack` (`UndoEntry`).
- `Undo` restores the last snapshot. `CancelTurn` restores the first one (the turn's checkpoint, after start-of-turn effects).
- `EndTurn` clears the stack: a finished turn is final.
- Actions that reveal hidden information (events in `engine/history.py: REVEALING_EVENTS`, e.g. drawing a card) clear the stack and become a new checkpoint, so nobody can peek and undo.
- Snapshots are shared between copies (`copy_state`), never deep-copied again.

## Choices (prompts)

Some effects need a decision: how much to invoke, which unit to hit, which scouted card to draw, how to split damage.

- An effect calls `ctx.ask(Prompt(...))`. If the answer isn't known yet, this raises `NeedChoice`.
- The engine then keeps the state from **before** the card was played and stores `state.pending = PendingChoice(seat, card_uid, answers, prompt)`. The card stays in the hand while the player chooses.
- `Respond(seat, answer)` replays the whole card from that state with all answers so far. Replay is deterministic because the RNG lives in the state. It either resolves completely (and pushes one undo entry) or stops at the next prompt.
- `CancelChoice` drops the pending card. It isn't allowed once hidden cards were shown during this card (scout, draw, market reveal): `ctx.ask` then marks the prompt `cancellable: false`.
- While a choice is pending, every other action is rejected with `error.choice_pending`.
- Prompt kinds: `number` (min..max), `choose_unit` (uids), `choose_card` (card views), `choose_cards` (list of uids, min..max), `split_damage` ({uid: amount}, optional `same_tier`), `order_cards` (all options in a new order, first = top), `choose_option` (index into `choose_one`), `choose_tier`. Optional (positive) effects set `allow_skip`, and the answer `null` skips them.
- `params.skip_key` names the skip button (e.g. `ui.prompt.skip_damage` = "Deal no damage"), so a player can play a damage spell just to get rid of it without hurting their own units.
- Only the acting player sees the prompt in their view. The others only see who is choosing and for which card.
- A `number` prompt with a single possible value (e.g. invoke with 0 mana) is answered automatically.

## Cards

### Two layers

- `CardDef`: static data loaded from YAML (id, type, cost, elements, stats, effects).
- `CardInstance`: a runtime copy with a unique `uid` that points to its `def_id`, plus mutable state: `current_hp`, `status` (`shield`, `stun`, `freeze` counts), `tapped`, `fixed_attack` / `fixed_health` (resolved invoke stats), and `effective_elements` (for the Mage element swap).

### IDs and file names

- Format: `<CLASS>-<SOURCE><NNN>` where NNN is the **printed card number**, which is unique across the whole game ("New card #"). Examples: `MAG-S001` (Mage starter, card 1), `MAG-P031` (Mage private market, card 31), `SHR-112` (shared market).
- Class codes: `MAG`, `ROB`, … (add as classes arrive). Shared cards use `SHR`.
- File name: `<ID>_<snake_case_name>.yaml`, e.g. `MAG-S03_scorch.yaml`.
- Every printed card has its own number and its own file, even identical ones (e.g. Mage starter 001–004 are four copies of the same fire influence). `number:` in the file repeats the printed number; `copies` stays 1 for numbered cards.
- IDs never change once assigned.

### Card file schema

```yaml
id: MAG-S003
number: 3                # printed card number, unique across all cards
type: spell              # influence | spell | unit
cost: 0                  # printed buy cost
elements: [fire]         # any of fire, water, wind, lightning, shadow; [all] for all five; [] for none
class: mage              # or "shared"
source: starter          # starter | private | shared | basic
copies: 2                # how many copies in the starting deck / market deck

# units only
attack: 0                # int, or {invoke: 0}
health: 2                # int, or {invoke: 1}  (= invoke + 1)

effects:                 # resolved in order on play, unless a trigger is given
  - do: deal_damage
    amount: {invoke: 0}
    target: {side: any, tiers: [1, 2, 3]}
  - if: {played_this_turn: {element: water, min: 2}}
    then:
      - do: grant_keyword
        keyword: split

triggers:                # units: ongoing abilities
  sot:  [{do: prepare}]
  eot:  []
  on_damage_taken: []
  on_kill: []
  on_card_played: []     # after each card its owner plays (while this unit is on the board)
  on_develop: []         # after this unit is developed (action or effect)

pre_effects: []          # units: resolved before invoke-based stats are set (e.g. 779)

modifiers:               # units: static, while on the board
  - spell_invoke_bonus: 1        # also: extra_attacks, develop_discount, thorns (damage to attackers),
                                 # stun_on_attack, freeze_on_attack, max_damage_per_hit, prepare_before_invoke,
                                 # taunt, cleave {freeze_if}, ally_thorns, ally_damage_reduction,
                                 # cheat_death {element, min}, shuffle_on_death

alt_cost: {lose_vp: 3}   # optional: the card may also be bought by losing VP (Buy with pay: vp)
hand_eot: {discard_for_vp: 1}   # optional: at your end of turn, may discard it from hand for VP
in_discard: {vp_per_kill: 1}    # optional: while in your discard pile (played cards count), VP per unit you kill
```

Choice text for `choose_one` lives in the locale too: `"options": ["Gain 4 inf", "Draw 2 cards", …]` next to `name` and `text`.

Display text (name, rules text) does **not** live in the card file. It lives in `data/locales/<lang>/cards.json` under the card ID:

```json
{
  "MAG-S003": { "name": "Scorch", "text": "Deal {invoke} damage. If you played at least 2 water cards this turn, gain **Split**." }
}
```

### Mandatory vs optional effects

From the rulebook: negative parts of a card are mandatory (and the card can't be played if they can't be met), positive and neutral parts are optional.

- Effects are optional by default (the player may skip them).
- Mark a mandatory effect with `required: true` (anywhere, also inside `if` / `choose_one` branches; a dry run follows the branch that would really happen). Its primitive must define `can_apply(state, seat, params)`; `check_play` refuses the card with `error.requirement_not_met` when it can't happen (e.g. 716 needs one of your units). A required effect's prompt has no skip (the effect gets `_required: true`).

## Effects

All card behaviour is composed from **effect primitives** implemented once in `engine/effects/`. Every primitive:

- is registered with `@effect("name")`,
- declares its required and optional params (validated when cards are loaded, so typos fail at startup),
- is a pure function `(ctx, params) -> list[Event]` that mutates state only through `ctx`,
- has unit tests in `tests/effects/`.

Initial primitive list (extend as cards require):

| Name | Params |
|---|---|
| `gain_inf` | `amount` |
| `gain_resource` / `lose_resource` | `amount` (class resource: mana, heat, …) |
| `gain_vp` | `amount` |
| `prepare` | optional `times`, `exceed_limit` (resource may go past the class limit, up to `hard_max`) |
| `deal_damage` | `amount`, `target`, optional `split: true` (or from `grant_keyword: split`), `if_killed: [effects]`, `different: true` (not a unit this card already hit) |
| `deal_damage_tier` | `amount`, optional `tiers` (or `source` = this unit's tier, no choice), `status` (token on each first), `spare_allies`, `exclude_self` |
| `heal` | `amount`, `target`, optional `max_hp` (cap; never lowers HP) |
| `shield` / `stun` / `freeze` | `target`, optional `count` (tokens), `units: N` (up to N different units), `all: true`, `heal` (HP for the chosen unit) |
| `develop` | optional `cost_override` (e.g. 0 = free): develop one of your units |
| `degrade` | `target`, optional `times` (value; choose again each time), `refund` (gain the develop cost of the tier the unit leaves), `per_opponent` (one unit of each other player) |
| `draw` | `count` |
| `scout` | `count`, optional `draw: 1`, `discard_any: true`, or `draw: 1` + `rest_choice: true` (discard the rest or put them back in any order) |
| `play_from_discard` | optional `card_type`: play a card from your discard pile not played this turn |
| `discard_from_hand` | optional `then`: you may discard 1 hand card (keeps the 2-card minimum); if you do, resolve `then` |
| `move_played_to_deck` | optional `element`, `position` (top/bottom): you may put one of your other cards played this turn into your deck |
| `next_spell_invoke_bonus` | `amount`, optional `element` + `element_amount` (printed elements) |
| `next_spell_twice` | optional `vp_per_kill`: next spell resolves twice with the same invoke value |
| `boost_attack` | `amount`: your units gain attack until end of turn |
| `vp_per_attack_kill` | `amount`: VP per enemy unit your units' attacks destroy this turn |
| `refresh_market` | `market: shared \| private \| all`, optional `times` or `up_to` (player picks 0..N); free |
| `discard_from_market` | `market`: a chosen market card goes to its removed pile; a new card fills the spot |
| `disrupt` | optional `card_type`, `count`: look at each other player's hand, choose card(s), they discard them |
| `reveal_for` | `element`, `count`, `then`: reveal hand cards (locked: can't be played this turn) to resolve `then` |
| `shuffle_into_deck` | `count`: choose up to N other cards from your discard pile, shuffle them into your deck |
| `heal_all` | `amount`, `target`: HP for every matching unit |
| `deal_damage_each_opponent` | `amount`, optional `tiers`: one chosen unit of each other player |
| `swap_units` | optional `heal`, `damage`, `per_opponent`: swap the places of 2 units |
| `boost_units` | `target`, optional `attack` (value), `extra_attacks`, `all`, `kill_vp` (you gain VP if its attack kills this turn): this turn only |
| `next_develop_discount` | — : your next development this turn costs 1 less per prepare this turn |
| `boost_self` | optional `attack`, `any_tier`: the unit with this ability, this turn |
| `pay_inf` | `amount` (use with `required: true`): pay inf as part of a card |
| `others_draw` | `count`: every other player draws |
| `bounce` | `target`, optional `random_discard`: unit back to its owner's hand (tokens are removed) |
| `resolve_market_card` | `max_cost`, optional `card_types`: copy a shared-market card's effects, then discard it from the market |
| `deal_damage_all` | `amount`, optional `spare_allies` |
| `status_damaged` | `status`: token on every unit this card harmed |
| `destroy_each_opponent` | optional `max_cost`: kill one unit of each other player (shields don't help) |
| `destroy_tier` | — : kill every unit on a chosen tier |
| `sacrifice_ally` | optional `transfer_hp`, `vp: tier_minus_one` |
| `heal_self` | `amount`: the unit with this ability gains HP |
| `move_self_to_tier` | `tier` (needs a free spot; usable with `required`) |
| `others_lose_vp` | `amount` (never below 0) |
| `influence_bonus` | `amount`: each other influence card played later this turn gives extra inf |
| `summon` | `attack`, `health`, `count` |
| `grant_keyword` | `keyword`, optional `scope` (e.g. `split` with `scope: same_tier`, for the rest of this card) |

Invoke isn't an effect: it's a value. `{invoke: N}` asks the class's invoke once per card (Mage: choose mana to spend; spells +1) and adds N (never below 0).

Card input in the format Jan uses (one row per printed card): `New card #`, `Current card #` (legacy, kept as a comment), `Element`, `Cost`, `Type`, `Affiliation`, `Card text`, `Attack`, `Health`.

Control structures, handled by the resolver rather than registered as effects: `if` / `then` / `else`, `repeat: <value>` + `effects` (e.g. "deal 2 dmg [invoke] times") and `choose_one: [[effects…], [effects…]]` (a `choose_option` prompt; an option may be `[]` for "don't"; optional `label: name` picks the option texts `cards.<id>.<name>` when a card has several choices).

Turn modifiers (`player.turn_modifiers`) hold "this turn" effects such as "your next spell…". They're consumed by the next spell (`engine/playing.py`) or cleared at the end of the turn. Temporary attack bonuses live on the unit (`temp_attack`) and reset at its owner's end of turn.

**Values** (`values.py`): an int, `{invoke: N}`, `{count: {played: {element, other}}}`, `{count: {unique_played_elements: {other}}}`, `{count: {ally_units: {min_tier}}}`, `{count: {ally_tiers: {}}}`, `{count: {prepares_this_turn: {}}}`, `{count: {enemy_kills_this_turn: {}}}`, `{count: {opponents: {}}}` (players − 1), `{count: {discard_cards: {}}}`, `{count: {discard_element: {element}}}`, `{count: {vp: {}}}`, `{count: {elements_at_least_twice: {other}}}`, `{sum: […]}`, `{mul: […]}`, `{max: […]}`, `{div_ceil: [a, b]}`, `{div_floor: [a, b]}` or `{min: [values…]}` ("max. 4" = `{min: [value, 4]}`). Unit `attack`/`health` may be values too (resolved once when the unit enters).

**Targets** (`targeting.py`): `{side: any | ally | enemy, tiers: [1, 2, 3, 4] | with_ally_units}`. Tokens count as tier 1. Allies and enemies alike unless `side` says otherwise.

**Conditions** (`conditions.py`): `played_this_turn {element | elements, min, other}`, `in_discard {element, min, other}`, `value_at_least {value, min}` (e.g. "invoke for 4"), `ally_tiers_at_least {min}`, `unique_played_elements_at_least {min, other}`, `played_matching {filter: non_primary | primary, min}`, `discard_count_at_least {min}`, `card_kills_at_least {min}` (units killed by this card so far), `source_on_tier {tier}`, `removed_this_turn {min}`.

An `if` block may carry `once_per_turn: true`: it's checked every time, fires the first time its condition is true, and then stays off until the end of the turn (tracked in `player.turn_flags`, per source unit).

**Adding a new mechanic:** add a primitive or condition once, test it, then reference it from any number of card files. Never special-case a card ID in engine code.

## Classes

`data/classes/<class>.yaml` describes the character board:

```yaml
id: mage
primary_elements: [fire, water]
resource: {key: mana, start: 0, limit: 4, hard_max: 7}
tiers:
  1: {spots: 2}
  2: {spots: 2, develop_cost: 3, vp: 1}
  3: {spots: 1, develop_cost: 4, vp: 2}
  4: {develop_cost: 5, vp: 3}            # spots = players − 1 (shared)
removal_costs: [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7]
passives:
  - trigger: sot
    effects: [{do: gain_resource, amount: 3}]
  - trigger: eot
    effects: [{do: lose_resource, amount: 3}]
  - modifier: spell_invoke_bonus
    amount: 1
  - modifier: element_swap_once_per_turn
prepare: [{do: gain_resource, amount: 1, up_to_limit: true}]
invoke: {mode: spend_resource_any}       # value = amount spent
```

Class-specific rules that don't fit the generic primitives go in `engine/classes/<class>.py` as small hook functions referenced from the YAML.

## Internationalisation

- Locale files: `data/locales/<lang>/*.json`. Only `en` for now.
- Keys are `<namespace>.<path>`, where the namespace is the file name: `ui.panel.end_turn`, `cards.MAG-S001.name`, `keywords.split.name`, `classes.mage.prepare`, `log.card_played`, `error.min_hand`.
- Client uses `t(key, params)` from `client/js/i18n.js`, with `{param}` interpolation and fallback to `en` when a key is missing.
- The server never sends display strings. Events and errors carry a key + params, e.g. `{"key": "log.attack", "params": {"attacker": "MAG-S005", "target": "ROB-S02", "damage": 2}}`.
- A test checks that every card ID, class and keyword has an `en` entry.

## Online play

- **Lobby:** "Create game" makes a room and returns a 6-character code (uppercase letters and digits, without the ambiguous characters 0/O and 1/I). Other players use "Join game" with that code and a display name.
- 2–4 players. The host chooses when to start. Classes are picked in the lobby, and each class can be picked once.
- Rooms live in memory. A player who reconnects with the same session token gets their seat back.
- One WebSocket per player. After each action the server broadcasts a fresh `PlayerView` to every player, plus the new `Event`s for animation and the log.

## UI design (approved)

The approved mockup is "board v2". Keep this layout unless told otherwise.

**Top bar.** Room code, round number, whose turn it is, and the player list with colour dots and VP.

**VP track.** A row of cells 0–30 (30 highlighted gold as the goal) with one coloured pawn per player on their current VP.

**Tier table** (centre of the screen):

- Columns: one per player (2–4). Column header shows the player colour, name and class.
- Rows from top to bottom: T4 (shared, spans all player columns, tinted gold, shows `players − 1` slots), then T3, T2, T1.
- Row label column shows the tier, VP per unit and develop cost.
- Empty spots are dashed outlines. The number of spots per player comes from their class.
- Each unit is a mini card. **Its border colour is the owner's player colour.** It shows the element icon(s), name, attack and current HP, and status icons with counts (shield, stun, freeze).
- Units the viewer can develop right now get a green outline and a green "↑ T{n} · {cost}" button. Clicking it develops the unit.
- Column headers show each player's end-of-turn VP preview ("EOT +N VP").
- Tapped units are slightly rotated and dimmed.

**Colour semantics** (keep these exclusive):

| Meaning | Colour |
|---|---|
| Player identity | one fixed colour per seat (blue, coral, purple, teal) on card borders, pawns, headers |
| Available, not yet used action | **green** outline (`--fill-success`) |
| Valid attack / effect target | red tint (`--bg-danger`) |
| Selected | accent blue outline |
| Tier 4 / VP goal | gold / warning tint |

Elements are shown as **icons**, never as colours, so they don't clash with player colours: fire = flame, water = droplet, wind = wind, lightning = bolt, shadow = moon.

**Shared market.** A row of 6 cards left → right. The price badge shows the adjusted price (`5+1` leftmost, `4−1` rightmost). Affordable cards get a green price badge. Cards the player can't afford are dimmed. Deck and removed counts are shown next to it. The free refresh is a green-outlined button until used.

**Private markets.** A tab per player in seat colour. Clicking a tab reveals that player's 3 private-market cards, and clicking it again hides them. The current player's own market is open by default and buyable. Other players' markets are view-only.

**Player panel** (bottom):

- Stats: **inf** (large, prominent), class resource with limit, current removal cost, elements played this turn (counts per element icon), deck / discard counts.
- Available-actions chips with a green outline (e.g. free refresh, Mage element swap, "N units can attack", affordable develops). Used ones turn grey and get a strikethrough.
- Hand as cards. The 2-card minimum is shown as a reminder slot.
- Turn buttons next to the hand: **Undo** (take back the last card played), **Cancel** (take back the whole turn so far) and **End turn** (commits the turn; can't be undone).

**Interactions.**

- Clicking an own unit that can attack highlights valid targets: same tier or one higher, never lower. Clicking a target attacks.
- Dragging a hand card **up** and releasing it anywhere on the screen above the hand plays the card. While dragging, a translucent drop zone covers the whole viewport above the hand (green if the card can be played, grey/red if not). Clicking a card doesn't play it.
- Dragging a hand card left or right moves it to the drop position and the other cards shift to make room (live, animated; e.g. dragging card 1 between 3 and 4 gives 2, 3, 1, 4, …). Hand order is cosmetic and client-side only (kept per game and seat in `sessionStorage`). New cards are added on the right.
- Hovering a card shows its full text. Hovering the class name shows passives, prepare and invoke.
- Prompts (targets, order of simultaneous effects, split damage) appear as an inline panel above the hand, not a blocking modal.

## Conventions

- Hand cards revealed by `reveal_for` are in `player.locked_cards` and can't be played this turn (`error.card_locked`).
- Format with `ruff format`, lint with `ruff`. Type-check with `mypy --strict` on `engine/`.
- Tests: `pytest`. Every effect primitive, condition and target selector has unit tests. Every card file is load-validated by a test.
- Keep the engine deterministic. Use only the state's RNG.
- Small commits with English messages in the imperative mood ("Add refresh_market effect").
- Keep code 3.10-compatible (no 3.11+-only syntax or stdlib features).
- When a rule is ambiguous, check `docs/RULES.md`. If it's still unclear, ask instead of guessing, then record the decision in `docs/DECISIONS.md`.

## Workflow for adding cards

1. Create `data/cards/<class>/<source>/<ID>_<name>.yaml`.
2. Add the name and text to `data/locales/en/cards.json`.
3. If the card needs a mechanic that doesn't exist yet, add the primitive or condition in `engine/` with tests first.
4. Run `pytest`. The data-validation test must pass.
