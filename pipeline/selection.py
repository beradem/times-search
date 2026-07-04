"""Deterministic daily puzzle selection.

Picks 3 distinct MM/YYYY pairs for an ET calendar date, seeded by that date so
everyone gets the same puzzle (Wordle-style). No pair may repeat within a
rolling 14-day window; the prior 13 days are read from a persisted ledger.
See PRD section 6.4.
"""
import datetime as dt
import hashlib
import json
import os
import random

from . import config

WINDOW_DAYS = 13          # 13 prior days + today = 2-calendar-week no-repeat
ROUNDS_PER_DAY = 3


def _seed(date_str):
    digest = hashlib.sha256(date_str.encode()).digest()
    return int.from_bytes(digest[:8], "big")


def load_ledger():
    if os.path.exists(config.LEDGER_PATH):
        with open(config.LEDGER_PATH) as f:
            return json.load(f)
    return {}


def save_ledger(ledger):
    os.makedirs(os.path.dirname(config.LEDGER_PATH), exist_ok=True)
    with open(config.LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2, sort_keys=True)


def _recent_pairs(ledger, date_str):
    """Set of (year, month) used in the 13 calendar days before date_str."""
    day = dt.date.fromisoformat(date_str)
    used = set()
    for i in range(1, WINDOW_DAYS + 1):
        prior = (day - dt.timedelta(days=i)).isoformat()
        for y, m in ledger.get(prior, []):
            used.add((y, m))
    return used


def select_pairs(date_str, ledger=None):
    """Return 3 distinct (year, month) pairs for date_str, honoring the
    rolling no-repeat window. Deterministic given (date_str, ledger)."""
    ledger = load_ledger() if ledger is None else ledger
    if date_str in ledger:  # idempotent: already chosen
        return [tuple(p) for p in ledger[date_str]]

    rng = random.Random(_seed(date_str))
    excluded = _recent_pairs(ledger, date_str)
    chosen = []
    while len(chosen) < ROUNDS_PER_DAY:
        pair = (rng.randint(config.ARCHIVE_MIN_YEAR, config.ARCHIVE_MAX_YEAR),
                rng.randint(1, 12))
        if pair >= config.ARCHIVE_START and pair not in excluded and pair not in chosen:
            chosen.append(pair)
    return chosen


def record(date_str, pairs, ledger=None):
    """Persist a day's selection to the ledger."""
    ledger = load_ledger() if ledger is None else ledger
    ledger[date_str] = [list(p) for p in pairs]
    save_ledger(ledger)
    return ledger
