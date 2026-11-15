"""Math problem generation. Pure logic, no UI -- keep it that way so it stays testable."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    prompt: str
    answer: int

    def check(self, raw: str) -> bool:
        try:
            return int(raw.strip()) == self.answer
        except ValueError:
            return False


def generate(difficulty: int, rng: random.Random | None = None) -> Problem:
    rng = rng or random.Random()
    if difficulty <= 1:
        ops, hi = "+-", 9
    elif difficulty == 2:
        ops, hi = "+-*", 20
    else:
        ops, hi = "+-*/", 99

    op = rng.choice(ops)
    a, b = rng.randint(1, hi), rng.randint(1, hi)

    if op == "+":
        return Problem(f"{a} + {b}", a + b)
    if op == "-":
        a, b = max(a, b), min(a, b)  # no negative answers
        return Problem(f"{a} - {b}", a - b)
    if op == "*":
        b = rng.randint(2, 12)
        return Problem(f"{a} × {b}", a * b)
    # Division: build from the answer so it's always exact.
    b = rng.randint(2, 12)
    q = rng.randint(2, 12)
    return Problem(f"{b * q} ÷ {b}", q)
