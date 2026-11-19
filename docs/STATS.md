# Market statistics

Recorded by `server/stats.py` for every game (dev and online). Locally the data goes to `.stats.db` (SQLite);
on the server to Turso when `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set.

## Tables

`games`: `id`, `code` (6-character join code), `mode` (`dev` / `online`), `created_at`, `finished_at`, `players`,
`classes` (JSON, class per seat), `seed`, `winners` (JSON seats), `rounds`.

`market_events`: one row per event.

| Column | Meaning |
|---|---|
| `game_id` | `games.id` |
| `round`, `turn_seat` | when it happened, and whose turn it was |
| `market` | `shared` or `private` |
| `market_owner`, `market_owner_class` | private market: whose market it is |
| `slot` | shared: 0 = leftmost (+1 inf) … 5 = rightmost (−1 inf); private: 0–2 |
| `card_id`, `card_number` | the card |
| `event` | `revealed`, `bought`, `bought_vp`, `left` |
| `buyer_seat`, `buyer_class` | who bought it |
| `price`, `modifier`, `vp_paid` | inf paid, the shared slot modifier (+1 / 0 / −1), VP paid for alternative-cost buys |
| `reason` | `revealed`: `setup` (on the table when the game started) or `refill`; `left`: `refresh`, `discarded`, `resolved` |

## Example queries

How each shared-market card was bought (at +1, at the printed price, at −1):

```sql
SELECT card_number,
       SUM(modifier = 1)  AS bought_plus_1,
       SUM(modifier = 0)  AS bought_normal,
       SUM(modifier = -1) AS bought_minus_1
FROM market_events
WHERE market = 'shared' AND event = 'bought'
GROUP BY card_number ORDER BY card_number;
```

How often a card is bought once it shows up:

```sql
SELECT card_number,
       SUM(event = 'revealed') AS seen,
       SUM(event IN ('bought', 'bought_vp')) AS bought,
       SUM(event = 'left') AS left_unbought,
       ROUND(1.0 * SUM(event IN ('bought', 'bought_vp')) / SUM(event = 'revealed'), 2) AS buy_rate
FROM market_events
GROUP BY card_number ORDER BY buy_rate DESC;
```

Delete the dev games:

```sql
DELETE FROM market_events WHERE game_id IN (SELECT id FROM games WHERE mode = 'dev');
DELETE FROM games WHERE mode = 'dev';
```

Locally: `sqlite3 .stats.db` (or any SQLite browser). Turso: `turso db shell <database-name>` or the Turso dashboard.
