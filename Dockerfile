# Vaporize server: FastAPI + the static client, one process (game rooms live in memory).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY engine engine
COPY server server
COPY client client
COPY data data

# Run as an unprivileged user; /app stays writable for the dev-game save file.
RUN useradd --create-home --uid 10001 vaporize && chown -R vaporize /app
USER vaporize

EXPOSE 8000

# One worker on purpose: games are kept in memory, so every request must reach the same process.
CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
