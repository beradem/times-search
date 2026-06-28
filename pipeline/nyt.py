"""Fetch and cache NYT Archive API months."""
import json
import os
import sys
import urllib.request

from . import config

ARCHIVE_URL = "https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={key}"


def fetch_month(year, month):
    """Return the list of article docs for a month, caching the raw response."""
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    path = os.path.join(config.CACHE_DIR, f"{year}-{month}.json")
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
    else:
        key = config.env("NYT_API_KEY", required=True)
        url = ARCHIVE_URL.format(year=year, month=month, key=key)
        print(f"  fetching {year}-{month:02d} from NYT (~20MB) ...", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=180) as r:
            data = json.load(r)
        with open(path, "w") as f:
            json.dump(data, f)
    return (data.get("response") or {}).get("docs") or []
