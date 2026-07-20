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
from .ranker import scrub_dates


def _extract_json(text):
    """Pull the first {...} object out of a model reply and parse it, tolerating
    markdown fences or stray prose around it."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except ValueError:
        return None

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
    '- "summary": ONE or TWO tight sentences in plain modern English explaining '
    "WHAT HAPPENED. Be concise — cut tangential side-details (do not list every "
    "city, sub-issue, or minor figure). Name the key people who are actually in "
    "the story, since they help date it. You MAY add a SHORT era-context phrase "
    "only if it fits naturally (e.g. 'during Reconstruction', 'in the aftermath "
    "of the Civil War', 'as the Cold War intensified'); never force it. Mention "
    "the sitting president ONLY if he is genuinely part of the story — do not "
    "tack him onto unrelated stories. Base facts on the headline and abstract; "
    "add only accurate, well-known context, and invent nothing.\n"
    "  HARD RULES: never state or imply the year, month, or decade ('the "
    "1870s'); no specific calendar dates ('February 14', 'the 14th'); no "
    "year-embedding events ('Panic of 1873', 'Election of 1876'); no comparison "
    "years. Clues are named people and light era context only.\n"
    '- "image_query": a short, specific phrase (3-6 words) to find a '
    "REPRESENTATIVE historical PHOTO of this exact event on Wikipedia (used "
    "privately; may include the year). Make it specific to the story's COUNTRY "
    "and place (e.g. 'United States coal miners 1890s', NOT just 'coal mining' "
    "which returns a British map), and pick a PHOTOGRAPHABLE subject — people, "
    "an event, a place — never an abstract concept, agreement, law, or map. "
    "E.g. '1943 Harlem riot', 'Apollo 11 moon landing'.\n"
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
            f"The U.S. president at the time was {pres} — use this to pick the "
            f"right era, but only NAME him in a summary if he is actually part "
            f"of that story. Use the year only in image_query, never in the "
            f"summary.\nRespond with ONLY the JSON object, nothing else.\n"
            f"Stories:\n{listing}")
    try:
        # Non-strict mode + tolerant parse: Groq's strict json_object mode
        # rejects the model's occasional malformed output with a 400; parsing
        # the JSON ourselves is more reliable.
        out = groq_client.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": user}],
            temperature=0.2, max_tokens=900)
        obj = _extract_json(out)
        arr = obj.get("stories", []) if obj else []
        if isinstance(arr, list) and len(arr) == len(stories):
            result = []
            for x, s in zip(arr, stories):
                summary = (scrub_dates(str(x.get("summary", "")).strip())
                           or scrub_dates(s["summary"]))
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
    return [{"summary": scrub_dates(s["summary"]), "image_query": "",
             "image_query_broad": ""}
            for s in stories]
