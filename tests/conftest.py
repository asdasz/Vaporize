"""Test-wide settings."""

from __future__ import annotations

import os

# Automated tests never write to the real statistics database (Turso or .stats.db): only games played by people
# are recorded. Tests that check the recorder use their own temporary SQLite file.
os.environ["VAPORIZE_STATS"] = "off"
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)
