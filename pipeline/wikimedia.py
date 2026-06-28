"""Find a free-licensed historical image from Wikipedia/Wikimedia for an event.

Used to give pre-2000 puzzles (which have no NYT photos) a reveal-screen image.
REVEAL-ONLY: never shown on the play screen, so the search query may include the
year to disambiguate the correct historical event. Results are cached on disk.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from . import config

API = "https://en.wikipedia.org/w/api.php"
# Wikimedia API etiquette requires a descriptive User-Agent.
UA = "times-search/0.1 (non-commercial educational history game)"
CACHE_PATH = os.path.join(config.CACHE_DIR, "wikimedia.json")


def _cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save(cache):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def find_image(query):
    """Return {url, source, page, title} for the best-matching page image, or
    None. Searches pages, takes the top result that has a thumbnail."""
    cache = _cache()
    if query in cache:
        return cache[query]

    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrlimit": "4", "gsrnamespace": "0",
        "prop": "pageimages|info", "piprop": "thumbnail",
        "pithumbsize": "1000", "inprop": "url",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    result = None
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        pages = (data.get("query") or {}).get("pages") or {}
        for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            thumb = p.get("thumbnail")
            if thumb and thumb.get("source"):
                result = {"url": thumb["source"], "source": "Wikimedia Commons",
                          "page": p.get("fullurl"), "title": p.get("title")}
                break
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  ! wikimedia lookup failed for {query!r} ({e})", file=sys.stderr)
        return None  # don't cache transient failures

    cache[query] = result
    _save(cache)
    return result
