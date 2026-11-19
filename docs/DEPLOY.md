# Deploying to Northflank

The server is one container (`Dockerfile`): FastAPI serves the API and the static client. Game rooms live in
memory, so run **exactly one instance**. Market statistics go to Turso (see `docs/STATS.md`).

## One-time setup

1. **Push the code** to GitHub (`asdasz/Vaporize`, branch `main`). Northflank builds from the repository.
2. **Link GitHub** in Northflank: Account settings → Git integrations → GitHub, and give it access to the
   `Vaporize` repository.
3. **Create a project**, e.g. `vaporize`, in a European region (the Turso database is in AWS EU West, Ireland).
4. **Create a secret group** in the project (Secrets → Add secret group), e.g. `turso`, type *runtime*, with:

   | Key | Value |
   |---|---|
   | `TURSO_DATABASE_URL` | `libsql://vaporize-asdasz.aws-eu-west-1.turso.io` |
   | `TURSO_AUTH_TOKEN` | the token created in the Turso dashboard (Read & Write, no expiry) |

   Never commit the token or paste it anywhere else.
5. **Create a combined service** (Create new → Service → Combined):
   - Name: `vaporize`
   - Repository: `asdasz/Vaporize`, branch `main`
   - Build: **Dockerfile**, path `/Dockerfile`, build context `/`
   - Networking: port `8000`, protocol HTTP, **public** (normally detected from `EXPOSE 8000`)
   - Resources: the smallest free plan; **instances: 1**
   - Advanced → Health checks (optional): HTTP, port `8000`, path `/api/health`
   - Create the service.

The first build starts right away. When it's running, the service header shows the public address
(`https://….code.run`). Open it on both computers.

## Playing online

1. Open the address and click **Host game**: enter your name, pick a class, **Create game**.
2. Click **Copy link** and send it to the other players (2–4 players in total).
3. They open the link, enter a name, pick a class and click **Join**. A 5th player is told all seats are taken.
4. When at least 2 players are in, the host clicks **Start game** (or waits for a 3rd and 4th).

Everyone sees only their own hand; the screen updates by itself within a second after anyone acts.
Reloading the page keeps your seat (in the same browser tab).

## Updates

Every push to `main` is built and deployed automatically (CI/CD is on by default for combined services).
A redeploy restarts the container, which **ends running games** (the save file lives inside the container).
Statistics in Turso are kept.

## Checking that statistics arrive

Turso dashboard → database `vaporize` → Edit Data: after a game has started, `games` and `market_events`
have rows. If not, check the service logs in Northflank for `Couldn't write … statistics statement(s)`
(usually a wrong URL or token).
