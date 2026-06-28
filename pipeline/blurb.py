"""Generate the reveal-screen 'this month in history' blurb via Groq.

Runs in the pre-generation pipeline (not at play time). Grounded strictly in
the month's extracted top stories to avoid hallucinated dates/events.
REVEAL-ONLY: never show this on the play screen — it would leak the answer.
"""
import sys
import urllib.error

from . import groq_client

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

SYSTEM = (
    "You write a 'this month in history' caption for a history game, shown "
    "AFTER the player has guessed. Given the top New York Times stories from a "
    "month, write a caption describing what was happening.\n"
    "STRICT RULES:\n"
    "- Write TWO or THREE sentences totaling 45-65 words. Be substantive and "
    "specific; do not be terse.\n"
    "- Use PAST tense throughout.\n"
    "- Open by naming the single most significant event directly. Do NOT begin "
    "with the month/year, 'This month', 'In <month>', or filler like 'It was'.\n"
    "- Neutral, factual, encyclopedic tone. Do not address the reader or "
    "mention the game, guessing, or 'this month in history'.\n"
    "- Use ONLY facts supported by the provided stories. Invent nothing.\n"
    "- Synthesize the stories into prose; do not list headlines verbatim.\n"
    "Return only the caption text."
)


def _fallback(stories):
    """If Groq is unavailable, degrade to a plain synthesis of the headlines."""
    leads = "; ".join(s["headline"].split(";")[0].strip() for s in stories[:3])
    return f"Among the month's major headlines: {leads}."


def generate(year, month, stories):
    listing = "\n".join(
        f"{i}. {s['headline']} — {s['summary']}".strip(" —")
        for i, s in enumerate(stories, 1)
    )
    user = f"Month: {MONTHS[month]} {year}\n\nTop stories:\n{listing}"
    try:
        return groq_client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": user}],
            temperature=0.2, max_tokens=200)
    except (urllib.error.URLError, KeyError, ValueError) as e:
        print(f"  ! Groq blurb failed ({e}); using fallback.", file=sys.stderr)
        return _fallback(stories)
