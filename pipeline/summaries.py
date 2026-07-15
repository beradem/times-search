"""Per-story enrichment via Groq: a clear play-screen summary AND a targeted
image search query.

The summary is shown on the PLAY screen, so it must NOT reveal the year/date.
The image_query is used privately (server-side) to find a representative photo,
so it MAY name the specific event and year. Both are grounded in the story.
"""
import json
import re
import sys
import urllib.error

from . import groq_client


def _scrub_years(text):
    """Safety net: strip any explicit 4-digit year from a summary, even a
    comparison year the model slipped in ('since the 1965 blackout')."""
    text = re.sub(r"\b(1[89]\d\d|20[0-2]\d)\b", "", text or "")
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Sitting U.S. president by (year, month) start — a reliable era anchor we feed
# the model so it doesn't have to (and can't mis-)guess it.
_PRESIDENTS = [
    (1850, 7, "Millard Fillmore"), (1853, 3, "Franklin Pierce"),
    (1857, 3, "James Buchanan"), (1861, 3, "Abraham Lincoln"),
    (1865, 4, "Andrew Johnson"), (1869, 3, "Ulysses S. Grant"),
    (1877, 3, "Rutherford B. Hayes"), (1881, 3, "James A. Garfield"),
    (1881, 9, "Chester A. Arthur"), (1885, 3, "Grover Cleveland"),
    (1889, 3, "Benjamin Harrison"), (1893, 3, "Grover Cleveland"),
    (1897, 3, "William McKinley"), (1901, 9, "Theodore Roosevelt"),
    (1909, 3, "William Howard Taft"), (1913, 3, "Woodrow Wilson"),
    (1921, 3, "Warren G. Harding"), (1923, 8, "Calvin Coolidge"),
    (1929, 3, "Herbert Hoover"), (1933, 3, "Franklin D. Roosevelt"),
    (1945, 4, "Harry S. Truman"), (1953, 1, "Dwight D. Eisenhower"),
    (1961, 1, "John F. Kennedy"), (1963, 11, "Lyndon B. Johnson"),
    (1969, 1, "Richard Nixon"), (1974, 8, "Gerald Ford"),
    (1977, 1, "Jimmy Carter"), (1981, 1, "Ronald Reagan"),
    (1989, 1, "George H. W. Bush"), (1993, 1, "Bill Clinton"),
    (2001, 1, "George W. Bush"), (2009, 1, "Barack Obama"),
    (2017, 1, "Donald Trump"),
]


def president_for(year, month):
    name = None
    for y, m, who in _PRESIDENTS:
        if (y, m) <= (year, month):
            name = who
        else:
            break
    return name


SYSTEM = (
    "You write clue-rich, plain-English descriptions of old New York Times "
    "stories for a history-guessing game. The player must guess the month and "
    "year, so each description should help them place the ERA — but must NEVER "
    "reveal the date. For every story return an object with:\n"
    '- "summary": 1-2 clear sentences in plain modern English explaining WHAT '
    "HAPPENED, written to help someone date the era. Name the key people "
    "involved; weave in the sitting U.S. president (given below) and the broad "
    "era or ongoing events when it helps (e.g. 'during Reconstruction', 'in the "
    "aftermath of the Civil War', 'as the Cold War intensified'). Base the core "
    "facts on the headline and abstract; you may add well-known, accurate "
    "historical context, but invent nothing you are unsure of.\n"
    "  HARD RULES: never state or imply the specific year or month; no 'in "
    "1878', 'this year', or a decade like 'the 1870s'. Never name an event, "
    "act, panic, or election that embeds a year (no 'Panic of 1873', 'Crash of "
    "1929', 'Election of 1876'). Never mention ANY year at all, not even the "
    "year of an earlier event referenced for comparison. Keep clues to named "
    "people and era-level context only.\n"
    '- "image_query": a short, specific phrase (3-6 words) to find a '
    "REPRESENTATIVE historical PHOTO of this exact event on Wikipedia (used "
    "privately; may include the year). E.g. '1943 Harlem riot', 'Apollo 11 "
    "moon landing'.\n"
    '- "image_query_broad": a BROADER subject guaranteed to have photos on '
    "Wikipedia (general theme, place, or era). NEVER empty. E.g. 'United States "
    "Congress 1870s', 'World War II home front'.\n"
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
    pres = president_for(year, month)
    user = (f"These stories are from {MONTHS[month]} {year}. "
            f"The U.S. president at the time was {pres}. Use the president and "
            f"era as clues in the summary, and the year only in image_query — "
            f"NEVER state the year or month in the summary.\nStories:\n{listing}")
    try:
        out = groq_client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": user}],
            temperature=0.2, max_tokens=800, json_mode=True)
        arr = json.loads(out).get("stories", [])
        if isinstance(arr, list) and len(arr) == len(stories):
            result = []
            for x, s in zip(arr, stories):
                summary = _scrub_years(str(x.get("summary", "")).strip()) or s["summary"]
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
