"""Per-story enrichment via Groq: a clear play-screen summary AND a targeted
image search query.

The summary is shown on the PLAY screen, so it must NOT reveal the year/date.
The image_query is used privately (server-side) to find a representative photo,
so it MAY name the specific event and year. Both are grounded in the story.
"""
import json
import sys
import urllib.error

from . import groq_client

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

SYSTEM = (
    "You prepare three things for each old New York Times story, for a history "
    "game. For every story return an object with:\n"
    '- "summary": a clear 1-2 sentence, plain modern-English description of '
    "WHAT HAPPENED, based ONLY on the given headline and abstract, inventing "
    "nothing. NEVER state or imply the year or date (the player must guess it) "
    "— no phrases like 'in 1943' or 'this year'.\n"
    '- "image_query": a short, specific phrase (3-6 words) to find a '
    "REPRESENTATIVE historical PHOTO of this exact event on Wikipedia. Name the "
    "concrete event/subject and, when it helps, the place and year (used "
    "privately, never shown). E.g. '1943 Harlem riot', 'World War II gasoline "
    "rationing', 'Apollo 11 moon landing'.\n"
    '- "image_query_broad": a BROADER subject that is guaranteed to have photos '
    "on Wikipedia — the general theme, place, or era of the story. This is the "
    "fallback so every story gets a picture, so it must NEVER be empty. E.g. "
    "'World War II United States home front', 'New York City 1940s', 'United "
    "States Congress', 'automobiles 1900s'.\n"
    'Return JSON: {"stories": [{"summary": "...", "image_query": "...", '
    '"image_query_broad": "..."}, ...]} in the same order you were given.'
)


def clarify(year, month, stories):
    """Return a list of {"summary", "image_query"} aligned to `stories`.
    Falls back to raw abstracts / no query if Groq is unavailable."""
    listing = "\n".join(
        f"{i}. HEADLINE: {s['headline']}\n   ABSTRACT: {s['summary'] or '(none)'}"
        for i, s in enumerate(stories, 1)
    )
    user = (f"These stories are from {MONTHS[month]} {year}. Use the year only "
            f"in image_query, never in summary.\nStories:\n{listing}")
    try:
        out = groq_client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": user}],
            temperature=0.2, max_tokens=600, json_mode=True)
        arr = json.loads(out).get("stories", [])
        if isinstance(arr, list) and len(arr) == len(stories):
            result = []
            for x, s in zip(arr, stories):
                summary = str(x.get("summary", "")).strip() or s["summary"]
                result.append({
                    "summary": summary,
                    "image_query": str(x.get("image_query", "")).strip(),
                    "image_query_broad": str(x.get("image_query_broad", "")).strip(),
                })
            return result
        print(f"  ! summaries count mismatch ({len(arr)} vs {len(stories)}); "
              "using raw abstracts.", file=sys.stderr)
    except (urllib.error.URLError, KeyError, ValueError) as e:
        print(f"  ! Groq summaries failed ({e}); using raw abstracts.", file=sys.stderr)
    return [{"summary": s["summary"], "image_query": "", "image_query_broad": ""}
            for s in stories]
