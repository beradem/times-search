"""Rewrite each story's cryptic NYT abstract into a clear, plain-English
description of what happened (1-2 sentences), so a modern player understands
the story at a glance.

Shown on the PLAY screen, so it must NOT reveal the year/date — the player has
to guess that. Grounded strictly in the headline + abstract; invents nothing.
"""
import json
import sys
import urllib.error

from . import groq_client

SYSTEM = (
    "You rewrite cryptic old New York Times article abstracts into clear, "
    "plain-English descriptions for a history game. For each story, write 1-2 "
    "sentences that make immediately clear WHAT HAPPENED.\n"
    "STRICT RULES:\n"
    "- 1-2 sentences each, plain modern English, no journalese abbreviations.\n"
    "- Base it ONLY on the given headline and abstract. Do NOT add facts, "
    "names, or context that aren't supported by them. Invent nothing.\n"
    "- NEVER state or imply the specific year or full date — the player must "
    "guess it. Do not write phrases like 'in 1969' or 'this year'.\n"
    "- Neutral, factual tone.\n"
    'Return JSON: {"summaries": ["...", "..."]} with one entry per story, in '
    "the same order you were given."
)


def clarify(year, month, stories):
    """Return a list of clarified 1-2 sentence summaries aligned to `stories`.
    Falls back to the raw abstracts if Groq is unavailable or malformed."""
    listing = "\n".join(
        f"{i}. HEADLINE: {s['headline']}\n   ABSTRACT: {s['summary'] or '(none)'}"
        for i, s in enumerate(stories, 1)
    )
    try:
        out = groq_client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": f"Stories:\n{listing}"}],
            temperature=0.2, max_tokens=400, json_mode=True)
        arr = json.loads(out).get("summaries", [])
        if isinstance(arr, list) and len(arr) == len(stories):
            return [str(x).strip() for x in arr]
        print(f"  ! summaries count mismatch ({len(arr)} vs {len(stories)}); "
              "using raw abstracts.", file=sys.stderr)
    except (urllib.error.URLError, KeyError, ValueError) as e:
        print(f"  ! Groq summaries failed ({e}); using raw abstracts.", file=sys.stderr)
    return [s["summary"] for s in stories]
