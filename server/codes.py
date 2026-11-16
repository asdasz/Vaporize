"""6-character join codes without ambiguous characters (0/O, 1/I)."""

from __future__ import annotations

import random
from collections.abc import Container

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def generate_code(rng: random.Random, taken: Container[str]) -> str:
    while True:
        code = "".join(rng.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if code not in taken:
            return code
