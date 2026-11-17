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

Open http://127.0.0.1:8000, pick 2, 3 or 4 players and play hot-seat. "Follow current player" switches the view to whoever's turn it is, and "Viewing as" lets you look at the board from any seat.

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
- [ ] Mage private market cards
- [x] Remove a card (from hand, played this turn or discard) on the 1, 1, 2, 2, … cost track
- [ ] Markets: buy, refresh
- [x] Units: develop (tier up for 3/4/5 inf, shared Tier 4) and VP scoring by tier at end of turn
- [ ] Units: attack, statuses
- [ ] Mage element swap passive
- [ ] Online lobby with 6-character join codes over WebSockets
