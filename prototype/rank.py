#!/usr/bin/env python3
"""Paper Guessr — iconicness ranker prototype.

Fetches one month of the NYT Archive API and ranks articles to surface the
~4 most "iconic" stories of that month, per PRD section 6.2.

Usage:
    python3 rank.py              # random month/year in 1851-2019
    python3 rank.py 1969 7       # specific year + month
"""
import json
import os
import random
import sys
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "prototype", "cache")


def load_key():
    env = os.path.join(ROOT, ".env")
    with open(env) as f:
        for line in f:
            if line.startswith("NYT_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("NYT_API_KEY not found in .env")


def fetch(year, month, key):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{year}-{month}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={key}"
    print(f"Fetching {year}-{month:02d} ... (can be ~20MB)", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r:
        data = json.load(r)
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# Material types that aren't "what happened this month" — drop these, keep the rest.
# (Allowlisting "News" fails on older archives where the type is literally "Article".)
SKIP_MATERIAL = {
    "op-ed", "editorial", "review", "letter", "letters", "correction",
    "caption", "obituary", "paid death notice: deaths", "list", "summary",
    "schedule", "marriage announcement", "text", "interview", "quote",
}


# Generic "wrapper" keywords NYT applies broadly; they're noise for topic clustering.
STOP_KEYWORDS = {
    "united states", "new york city", "new york state", "deaths", "editorials",
    "politics and government", "international relations", "finances",
    "united states international relations", "u.s.", "front page",
    "addresses, letters and statements", "law and legislation",
}
# Any keyword appearing on more than this fraction of the month's docs is treated
# as generic boilerplate (e.g. "ASTRONAUTICS", "UNITED STATES PROJECTS").
GENERIC_DF = 0.05


def front_weight(page):
    return 1.0 if page == 1 else (0.5 if page in (2, 3) else 0.0)


def headline_richness(headline, page):
    """Importance proxy for the pre-~1930 keyword desert. Lead stories of that
    era ran long, multi-deck, ALL-CAPS headlines; filler ran short one-liners."""
    letters = [c for c in headline if c.isalpha()]
    caps = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0
    decks = headline.count(";") + headline.count(" -- ") + headline.count("--")
    length = min(len(headline) / 200.0, 1.0)
    return (0.40 * front_weight(page) + 0.25 * length +
            0.20 * min(decks / 4.0, 1.0) + 0.15 * caps)


def _sig_words(headline):
    return {w for w in "".join(c.lower() if c.isalnum() else " "
                               for c in headline).split() if len(w) > 3}


def _too_similar(headline, chosen, thresh=0.4):
    """Jaccard overlap of significant words — de-dupes same-event front-pagers
    when we have no topic keywords to cluster on."""
    words = _sig_words(headline)
    for c in chosen:
        other = _sig_words(c["headline"])
        if words and other:
            j = len(words & other) / len(words | other)
            if j >= thresh:
                return True
    return False


def score_articles(docs):
    # --- Pass 1: month-wide keyword frequency + total doc count for DF filtering ---
    kw_freq = Counter()
    for d in docs:
        for k in d.get("keywords") or []:
            val = k.get("value")
            if val:
                kw_freq[val] += 1
    n = len(docs) or 1
    kw_ratio = sum(1 for d in docs if d.get("keywords")) / n
    generic = {k for k, c in kw_freq.items()
               if c / n > GENERIC_DF or k.lower() in STOP_KEYWORDS}
    max_cov = max((c for k, c in kw_freq.items() if k not in generic), default=1) or 1

    scored = []
    for d in docs:
        if d.get("document_type") not in (None, "article"):
            continue
        if (d.get("type_of_material") or "").lower() in SKIP_MATERIAL:
            continue

        page = as_int(d.get("print_page"))
        kws = [k.get("value") for k in (d.get("keywords") or []) if k.get("value")]
        specific = [k for k in kws if k not in generic]
        # The article's topic = its most-covered *specific* keyword.
        topic = max(specific, key=lambda v: kw_freq[v]) if specific else None
        coverage = kw_freq[topic] if topic else 0
        headline = (d.get("headline") or {}).get("main") or "(no headline)"

        scored.append({
            "score": 0.55 * (coverage / max_cov) + 0.45 * front_weight(page),
            "richness": headline_richness(headline, page),
            "headline": headline,
            "abstract": d.get("abstract") or d.get("snippet") or "",
            "page": page,
            "desk": d.get("news_desk") or d.get("section_name") or "",
            "coverage": coverage,
            "topic": topic,
            "has_img": bool(d.get("multimedia")),
            "url": d.get("web_url"),
            "_hlen": len(headline),
        })

    return scored, kw_ratio


def pick_top4(scored):
    """Cluster by topic, rank clusters by coverage, pick each cluster's best
    front-page representative (front page first, then richest headline)."""
    clusters = {}
    for a in scored:
        key = a["topic"] or f"_solo:{a['headline']}"
        clusters.setdefault(key, []).append(a)

    # Best representative within a cluster: front page, then longest headline.
    reps = []
    for arts in clusters.values():
        rep = max(arts, key=lambda a: (front_weight(a["page"]), a["_hlen"]))
        rep = dict(rep, cluster_size=len(arts))
        reps.append(rep)

    # Rank clusters by coverage volume, then front-page strength.
    reps.sort(key=lambda a: (a["coverage"], front_weight(a["page"])), reverse=True)
    return reps[:4]


def pick_by_headline(scored):
    """Keyword-desert fallback: rank by headline richness, de-dupe same-event
    front-pagers by significant-word overlap."""
    ranked = sorted(scored, key=lambda a: a["richness"], reverse=True)
    chosen = []
    for a in ranked:
        if _too_similar(a["headline"], chosen):
            continue
        chosen.append(dict(a, cluster_size=1))
        if len(chosen) == 4:
            break
    return chosen


# Below this share of articles carrying keywords, we're in the desert and
# switch to the headline-richness heuristic.
KEYWORD_DESERT_THRESHOLD = 0.10


def main():
    key = load_key()
    if len(sys.argv) == 3:
        year, month = int(sys.argv[1]), int(sys.argv[2])
    else:
        year, month = random.randint(1851, 2019), random.randint(1, 12)

    data = fetch(year, month, key)
    docs = (data.get("response") or {}).get("docs") or []
    print(f"\n=== {year}-{month:02d}  ({len(docs)} total docs) ===\n")

    scored, kw_ratio = score_articles(docs)
    if kw_ratio < KEYWORD_DESERT_THRESHOLD:
        mode, top4 = "headline-richness (keyword desert)", pick_by_headline(scored)
    else:
        mode, top4 = "topic clusters", pick_top4(scored)
    print(f"[mode: {mode} | keyword coverage: {kw_ratio:.0%}]\n")
    for i, a in enumerate(top4, 1):
        print(f"{i}. {a['headline']}")
        if a["abstract"]:
            print(f"     {a['abstract'][:160]}")
        print(f"     page={a['page']} desk={a['desk']!r} topic={a['topic']!r} "
              f"coverage={a['coverage']} cluster={a['cluster_size']} img={a['has_img']}")
        print()


if __name__ == "__main__":
    main()
