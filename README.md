# Vaporize

Online deck-building card game for 2–4 players. Rules: [`docs/RULES.md`](docs/RULES.md). Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).

## Run locally

Requires Python 3.10+ (developed on 3.14).

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn server.app:app --reload --reload-dir engine --reload-dir server --reload-dir data
```

`--reload-dir` limits auto-restarts to Python code and game data (not tests or the client, which is served as static files). Dev games are saved to `.devgames.pkl`, so they survive restarts.

Open http://127.0.0.1:8000 and click **Host game** (send the link to the others, or open it in a second tab), or use **Local test game** to pick 2, 3 or 4 players and play hot-seat. "Follow current player" switches the view to whoever's turn it is, and "Viewing as" lets you look at the board from any seat.

## Market statistics

Every game records which cards were revealed in, bought from (and at which price modifier) or left the shared
and private markets. Locally they go to `.stats.db` (SQLite: `sqlite3 .stats.db`). Schema and example queries:
[`docs/STATS.md`](docs/STATS.md).

On the server, set these environment variables (as secrets, never in the repo) to write to Turso instead:

```bash
TURSO_DATABASE_URL=libsql://<database>-<org>.turso.io
TURSO_AUTH_TOKEN=<token from `turso db tokens create <database>`>
```

`VAPORIZE_STATS=off` turns recording off.

## Deploy

One Docker container (`Dockerfile`) on Northflank, statistics in Turso: step-by-step guide in
[`docs/DEPLOY.md`](docs/DEPLOY.md).

## Tests

```bash
pytest
ruff check . && ruff format --check .
mypy
```

## Status

- [x] Engine core: zones (deck, hand, in play, discard, removed, markets, tiers), card/class loading from YAML
- [x] Card play loop: play up to 5 of 7, discard, draw back to 7 with reshuffle, smaller hand when nothing is left
- [x] Board UI draft for 2–4 players (tier table, VP track, markets, hand), hot-seat dev API
- [x] Turn controls: drag a card up to play it, Undo, Cancel turn, End turn (final); drag to reorder the hand
- [x] Mage starter deck (cards 001–012) with invoke, scout, damage + split, heal, prepare
- [x] Choice prompts (invoke amount, targets, scouted card, split damage)
- [x] Mage private market cards (031–045)
- [x] Remove a card (from hand, played this turn or discard) on the 1, 1, 2, 2, … cost track
- [x] Markets: buy, refresh (shared refresh free once per turn)
- [x] Basic supply pile (701–712, always buyable)
- [x] Shared market cards (713–811, no 800)
- [x] Units: develop (tier up for 3/4/5 inf, shared Tier 4) and VP scoring by tier at end of turn
- [x] Units: attacks (same tier or one higher)
- [x] Status effects from cards (shield, stun, freeze)
- [x] Mage element swap passive (free, once per turn)
- [x] Monarch class (cards 101–112, 131–145)
- [x] Market statistics database (SQLite locally, Turso on the server)
- [x] Online lobby: host / join with a link or 6-character code, 2–4 players, host starts
- [ ] WebSockets instead of polling
