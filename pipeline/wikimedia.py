"""Find free-licensed historical images from Wikipedia / Wikimedia Commons.

Returns candidate lists (not just one) so the builder can de-duplicate images
within a round and still keep every card topical. Results are cached on disk.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

_MIN_INTERVAL = 0.4   # seconds between Wikimedia requests (be a good citizen)
_last = [0.0]

WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = "paper-guessr/0.1 (non-commercial educational history game)"
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


def _get(api, params, retries=4):
    url = api + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        wait = _MIN_INTERVAL - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))  # back off on rate limit
                continue
            raise


def find_images(query, limit=5):
    """Lead images of the top Wikipedia pages matching `query` — curated and
    usually the best single photo of a subject. Returns [{url, title, source}]."""
    key = f"wiki:{query}"
    cache = _cache()
    if key in cache:
        return cache[key]
    out = []
    try:
        data = _get(WIKI, {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrlimit": str(limit), "gsrnamespace": "0",
            "prop": "pageimages|info", "piprop": "thumbnail",
            "pithumbsize": "1000", "inprop": "url",
        })
        pages = (data.get("query") or {}).get("pages") or {}
        for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            thumb = p.get("thumbnail")
            if thumb and thumb.get("source"):
                out.append({"url": thumb["source"], "title": p.get("title"),
                            "source": "Wikimedia Commons"})
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  ! wiki lookup failed for {query!r} ({e})", file=sys.stderr)
        return []  # don't cache transient failures
    cache[key] = out
    _save(cache)
    return out


def commons_images(query, limit=8):
    """Actual photo files from Wikimedia Commons matching `query` — many distinct
    images per subject, ideal for giving same-event stories different photos."""
    key = f"commons:{query}"
    cache = _cache()
    if key in cache:
        return cache[key]
    out = []
    try:
        data = _get(COMMONS, {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrlimit": str(limit), "gsrnamespace": "6",
            "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": "1000",
        })
        pages = (data.get("query") or {}).get("pages") or {}
        for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            mime = ii.get("mime", "")
            url = ii.get("thumburl") or ii.get("url")
            # photos only — skip diagrams/flags/maps (svg) and non-images
            if url and mime.startswith("image/") and mime != "image/svg+xml":
                out.append({"url": url, "title": p.get("title", ""),
                            "source": "Wikimedia Commons"})
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        print(f"  ! commons lookup failed for {query!r} ({e})", file=sys.stderr)
        return []
    cache[key] = out
    _save(cache)
    return out


def find_image(query):
    """Backwards-compatible single best image, or None."""
    imgs = find_images(query, limit=4)
    if imgs:
        return {**imgs[0], "page": None}
    return None
