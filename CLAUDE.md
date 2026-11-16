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
| Language | Python 3.12+ | Type hints everywhere, `from __future__ import annotations` |
| Server | FastAPI + WebSockets (uvicorn) | Authoritative: all rules run on the server |
| Data models | Pydantic v2 | Card/class definitions, network messages |
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
│   │   ├── shared/              # shared-market cards
│   │   │   └── SHR-001_spark.yaml
│   │   ├── mage/
│   │   │   ├── starter/         # MAG-S01 … (12 cards incl. copies)
│   │   │   └── private/         # MAG-P01 … MAG-P15
│   │   └── robot/ …
│   ├── classes/
│   │   └── mage.yaml            # character board: tiers, resource, passives, prepare, invoke
│   └── locales/
│       └── en/
│           ├── ui.json          # UI strings
│           ├── cards.json       # card names + rules text, keyed by card ID
│           ├── classes.json     # class names, passives, prepare/invoke text
│           └── keywords.json    # keyword names + reminder text
├── engine/
│   ├── state.py                 # GameState, PlayerState, MarketState, Board
│   ├── zones.py                 # Zone (ordered pile) + helpers
│   ├── cards.py                 # CardDef (static) and CardInstance (runtime)
│   ├── loader.py                # loads + validates YAML into CardDef / ClassDef
│   ├── actions.py               # player actions: play, buy, refresh, remove, develop, attack, end_turn, respond
│   ├── turn.py                  # SOT → actions → EOT sequencing, round + game end
│   ├── combat.py                # attack range, damage, shields, destruction
│   ├── effects/
│   │   ├── registry.py          # @effect("name") decorator + lookup
│   │   ├── resources.py         # gain_inf, gain_resource, lose_resource, gain_vp, …
│   │   ├── damage.py            # deal_damage, heal, split handling
│   │   ├── status.py            # shield, stun, freeze
│   │   ├── movement.py          # develop, degrade
│   │   ├── cards.py             # draw, scout, disrupt, discard, remove
│   │   ├── market.py            # refresh_market
│   │   ├── units.py             # summon
│   │   └── class_hooks.py       # invoke, prepare (delegate to ClassDef)
│   ├── conditions.py            # played_this_turn, in_discard, has_unit_on_tier, …
│   ├── targeting.py             # target selectors (ally/enemy/any, tier ranges)
│   ├── values.py                # value expressions: literal, invoke, invoke+N, count_of(…)
│   ├── events.py                # Event types (for log + client animations)
│   ├── prompts.py               # Prompt / PromptResponse types
│   └── view.py                  # GameState → PlayerView (redaction)
├── server/
│   ├── app.py                   # FastAPI app, static files, WebSocket endpoint
│   ├── rooms.py                 # Room registry, 6-char join codes
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

**Board** (`Board`)

- `tiers[player_id][1..3]`: per-player tier slots; spot counts come from the player's `ClassDef`.
- `tier4`: shared, `players − 1` slots.
- `tokens[player_id]`: summoned token units. They count as Tier 1 but don't use a Tier 1 spot.

Rule notes the engine must respect:

- "In your discard pile" counts `discard + in_play`. Cards played this turn are already counted as discarded for queries and for the remove action.
- "Played this turn" conditions count only cards in `in_play` **before** the current card (order matters).
- When the deck is empty and a draw/scout is needed, shuffle `discard` into `deck` first.
- Destroyed units go to the owner's `discard`. Destroyed tokens are deleted.

## Cards

### Two layers

- `CardDef`: static data loaded from YAML (id, type, cost, elements, stats, effects).
- `CardInstance`: a runtime copy with a unique `uid` that points to its `def_id`, plus mutable state: `current_hp`, `status` (`shield`, `stun`, `freeze` counts), `tapped`, `fixed_attack` / `fixed_health` (resolved invoke stats), and `effective_elements` (for the Mage element swap).

### IDs and file names

- Format: `<CLASS>-<SOURCE><NN>`. Examples: `MAG-S01` (Mage starter), `MAG-P07` (Mage private), `SHR-012` (shared market).
- Class codes: `MAG`, `ROB`, … (add as classes arrive). Shared cards use `SHR`.
- File name: `<ID>_<snake_case_name>.yaml`, e.g. `MAG-S03_scorch.yaml`.
- The ID is the printed card number. IDs never change once assigned. Duplicates in a deck are expressed with `copies:` in the file, not with extra files.

### Card file schema

```yaml
id: MAG-S03
type: spell              # influence | spell | unit
cost: 0                  # printed buy cost
elements: [fire]         # any of fire, water, wind, lightning, shadow; [all] for all five; [] for none
class: mage              # or "shared"
source: starter          # starter | private | shared
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
```

Display text (name, rules text) does **not** live in the card file. It lives in `data/locales/<lang>/cards.json` under the card ID:

```json
{
  "MAG-S03": { "name": "Scorch", "text": "Deal {invoke} damage. If you played at least 2 water cards this turn, gain **Split**." }
}
```

### Mandatory vs optional effects

From the rulebook: negative parts of a card are mandatory (and the card can't be played if they can't be met), positive and neutral parts are optional.

- Effects are optional by default (the player may skip them).
- Mark a mandatory effect with `required: true`. The engine checks every required effect before the card can be played.

## Effects

All card behaviour is composed from **effect primitives** implemented once in `engine/effects/`. Every primitive:

- is registered with `@effect("name")`,
- declares a Pydantic params model (validated when cards are loaded, so typos fail at startup),
- is a pure function `(ctx, params) -> list[Event]` that mutates state only through `ctx`,
- has unit tests in `tests/effects/`.

Initial primitive list (extend as cards require):

| Name | Params |
|---|---|
| `gain_inf` | `amount` |
| `gain_resource` / `lose_resource` | `amount` (class resource: mana, heat, …) |
| `gain_vp` | `amount` |
| `invoke` | value expression consumer, see `values.py` |
| `prepare` | none (delegates to the class) |
| `deal_damage` | `amount`, `target`, optional `split` |
| `heal` | `amount`, `target` |
| `shield` / `stun` / `freeze` | `count`, `target` |
| `develop` / `degrade` | `target`, optional `cost_override`, `tiers` |
| `draw` | `count` |
| `scout` | `count` |
| `disrupt` | `target_player` |
| `refresh_market` | `market: shared \| private` |
| `summon` | `attack`, `health`, `count` |
| `grant_keyword` | `keyword` (e.g. `split` for the rest of this card) |

Control structures, handled by the resolver rather than registered as effects: `if` / `then` / `else`, `choose_one`, `repeat`.

**Values** (`values.py`) can be an int, `{invoke: N}` (invoke + N), or counters such as `{count: {in_discard: {element: water}}}`.

**Conditions** (`conditions.py`): `played_this_turn {element, min, other: true}`, `in_discard {element, min}`, `has_unit_on_tier {tier}`, `resource_at_least {amount}`, …

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
- Keys are dotted and stable: `ui.lobby.create_game`, `ui.actions.end_turn`, `keyword.split.name`, `class.mage.passive.1`.
- Client uses `t(key, params)` from `client/js/i18n.js`, with `{param}` interpolation and fallback to `en` when a key is missing.
- The server never sends display strings. Events and errors carry a key + params, e.g. `{"key": "log.attack", "params": {"attacker": "MAG-S05", "target": "ROB-S02", "damage": 2}}`.
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
- "End turn" button.

**Interactions.**

- Clicking an own unit that can attack highlights valid targets: same tier or one higher, never lower. Clicking a target attacks.
- Hovering a card shows its full text. Hovering the class name shows passives, prepare and invoke.
- Prompts (targets, order of simultaneous effects, split damage) appear as an inline panel above the hand, not a blocking modal.

## Conventions

- Format with `ruff format`, lint with `ruff`. Type-check with `mypy --strict` on `engine/`.
- Tests: `pytest`. Every effect primitive, condition and target selector has unit tests. Every card file is load-validated by a test.
- Keep the engine deterministic. Use only the state's RNG.
- Small commits with English messages in the imperative mood ("Add refresh_market effect").
- When a rule is ambiguous, check `docs/RULES.md`. If it's still unclear, ask instead of guessing, then record the decision in `docs/DECISIONS.md`.

## Workflow for adding cards

1. Create `data/cards/<class>/<source>/<ID>_<name>.yaml`.
2. Add the name and text to `data/locales/en/cards.json`.
3. If the card needs a mechanic that doesn't exist yet, add the primitive or condition in `engine/` with tests first.
4. Run `pytest`. The data-validation test must pass.
