"""Generate the reveal-screen 'this month in history' blurb via Groq.

Runs in the pre-generation pipeline (not at play time). Grounded strictly in
the month's extracted top stories to avoid hallucinated dates/events.
REVEAL-ONLY: never show this on the play screen — it would leak the answer.
"""
import json
import sys
import urllib.error
import urllib.request

from . import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

SYSTEM = (
    "You write a short 'this month in history' caption for a history guessing "
    "game, shown AFTER the player has guessed. You are given the top New York "
    "Times stories from a specific month. Write 2-3 engaging sentences "
    "describing what was happening that month, based ONLY on the provided "
    "headlines and summaries. Do not invent events, people, or dates that the "
    "stories do not support. Synthesize; do not just list the headlines."
)


def _fallback(stories):
    """If Groq is unavailable, degrade to a plain synthesis of the headlines."""
    leads = "; ".join(s["headline"].split(";")[0].strip() for s in stories[:3])
    return f"Among the month's major headlines: {leads}."


def generate(year, month, stories):
    key = config.env("GROQ_API_KEY", required=True)
    listing = "\n".join(
        f"{i}. {s['headline']} — {s['summary']}".strip(" —")
        for i, s in enumerate(stories, 1)
    )
    user = f"Month: {MONTHS[month]} {year}\n\nTop stories:\n{listing}"
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
        "temperature": 0.5,
        "max_tokens": 220,
    }).encode()
    req = urllib.request.Request(
        GROQ_URL, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 # Cloudflare blocks the default Python-urllib UA (error 1010).
                 "User-Agent": "times-search/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        print(f"  ! Groq blurb failed ({e}); using fallback.", file=sys.stderr)
        return _fallback(stories)
