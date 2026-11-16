# Vaporize

Online deck-building card game for 2–4 players. Rules: [`docs/RULES.md`](docs/RULES.md). Architecture and conventions: [`CLAUDE.md`](CLAUDE.md).

## Run locally

Requires Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn server.app:app --reload
```

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
- [ ] Real Mage cards (current starter deck is mock data)
- [ ] Markets: buy, refresh, remove card
- [ ] Units: develop, attack, statuses
- [ ] Invoke / prepare, class passives with modifiers
- [ ] Online lobby with 6-character join codes over WebSockets
