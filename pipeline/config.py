"""Paths and environment configuration for the pipeline."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Reuse the prototype's download cache so we don't re-fetch ~20MB months.
CACHE_DIR = os.path.join(ROOT, "prototype", "cache")
# Puzzles are served by the web app, so they live under web/ (the deploy root).
PUZZLE_DIR = os.path.join(ROOT, "web", "puzzles")
# Ledger is internal state — kept OUTSIDE web/ so it isn't publicly served.
LEDGER_PATH = os.path.join(ROOT, "data", "ledger.json")

ARCHIVE_MIN_YEAR = 1851
ARCHIVE_MAX_YEAR = 2019
# The NYT's first issue was September 18, 1851 — earlier months return no
# articles, so puzzle selection must not draw them.
ARCHIVE_START = (1851, 9)

_ENV_CACHE = None


def _load_env():
    """Parse .env once into a dict (no external deps)."""
    global _ENV_CACHE
    if _ENV_CACHE is None:
        _ENV_CACHE = {}
        path = os.path.join(ROOT, ".env")
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        _ENV_CACHE[k.strip()] = v.strip()
    return _ENV_CACHE


def env(key, default=None, required=False):
    val = os.environ.get(key) or _load_env().get(key) or default
    if required and not val:
        raise SystemExit(f"Missing required key {key} (set it in .env)")
    return val


GROQ_MODEL = env("GROQ_MODEL", "llama-3.3-70b-versatile")
