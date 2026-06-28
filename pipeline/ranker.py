"""Iconicness ranker — selects the ~4 defining stories of a month.

Ported from the validated prototype/rank.py. Two modes:
  * topic clustering   (~1930+, where keyword coverage is rich)
  * headline richness  (pre-~1930 "keyword desert" fallback)
See PRD section 6.2 / 6.3.
"""
from collections import Counter

# Material types that aren't "what happened this month" — drop, keep the rest.
SKIP_MATERIAL = {
    "op-ed", "editorial", "review", "letter", "letters", "correction",
    "caption", "obituary", "paid death notice: deaths", "list", "summary",
    "schedule", "marriage announcement", "text", "interview", "quote",
}
# Generic "wrapper" keywords NYT applies broadly; noise for topic clustering.
STOP_KEYWORDS = {
    "united states", "new york city", "new york state", "deaths", "editorials",
    "politics and government", "international relations", "finances",
    "united states international relations", "u.s.", "front page",
    "addresses, letters and statements", "law and legislation",
}
GENERIC_DF = 0.05            # keyword on >5% of docs => boilerplate
KEYWORD_DESERT_THRESHOLD = 0.10  # below this keyword coverage => headline mode

STATIC_PREFIX = "https://static01.nyt.com/"
PREFERRED_CROPS = ("superJumbo", "articleLarge", "threeByTwoSmallAt2X", "popup")


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def front_weight(page):
    return 1.0 if page == 1 else (0.5 if page in (2, 3) else 0.0)


def headline_richness(headline, page):
    """Importance proxy for the pre-~1930 keyword desert: lead stories ran long,
    multi-deck, ALL-CAPS headlines; filler ran short one-liners."""
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
    words = _sig_words(headline)
    for c in chosen:
        other = _sig_words(c["headline"])
        if words and other and len(words & other) / len(words | other) >= thresh:
            return True
    return False


def pick_image(doc):
    """Best image URL for a doc, or None. Handles relative legacy paths."""
    candidates = []
    for m in doc.get("multimedia") or []:
        url = m.get("url")
        if not url:
            continue
        w = as_int(m.get("width")) or 0
        crop = m.get("crop_name") or ""
        # Sort key: preferred crops first, then widest image.
        order = PREFERRED_CROPS.index(crop) if crop in PREFERRED_CROPS else 99
        candidates.append(((order, -w), url))
    if not candidates:
        return None
    url = min(candidates)[1]
    return url if url.startswith("http") else STATIC_PREFIX + url.lstrip("/")


def _story(doc, page, topic=None, cluster_size=1):
    headline = (doc.get("headline") or {}).get("main") or "(no headline)"
    return {
        "headline": headline,
        "summary": doc.get("abstract") or doc.get("snippet") or "",
        "image": pick_image(doc),
        "url": doc.get("web_url"),
        "page": page,
        "topic": topic,
        "cluster_size": cluster_size,
        "_hlen": len(headline),
        "_richness": headline_richness(headline, page),
    }


def _candidate_docs(docs):
    for d in docs:
        if d.get("document_type") not in (None, "article"):
            continue
        if (d.get("type_of_material") or "").lower() in SKIP_MATERIAL:
            continue
        yield d


def rank_month(docs):
    """Return up to 4 distinct top stories for the month, plus metadata.

    Returns (stories, meta) where meta = {"mode", "keyword_coverage"}.
    """
    n = len(docs) or 1
    kw_freq = Counter()
    for d in docs:
        for k in d.get("keywords") or []:
            if k.get("value"):
                kw_freq[k["value"]] += 1
    kw_ratio = sum(1 for d in docs if d.get("keywords")) / n

    if kw_ratio < KEYWORD_DESERT_THRESHOLD:
        stories = _rank_by_headline(docs)
        mode = "headline-richness"
    else:
        stories = _rank_by_clusters(docs, kw_freq, n)
        mode = "topic-clusters"
    return stories, {"mode": mode, "keyword_coverage": round(kw_ratio, 3)}


def _rank_by_clusters(docs, kw_freq, n):
    generic = {k for k, c in kw_freq.items()
               if c / n > GENERIC_DF or k.lower() in STOP_KEYWORDS}
    clusters = {}
    for d in _candidate_docs(docs):
        page = as_int(d.get("print_page"))
        kws = [k.get("value") for k in (d.get("keywords") or []) if k.get("value")]
        specific = [k for k in kws if k not in generic]
        topic = max(specific, key=lambda v: kw_freq[v]) if specific else None
        key = topic or f"_solo:{(d.get('headline') or {}).get('main')}"
        clusters.setdefault(key, {"docs": [], "topic": topic})["docs"].append((d, page))

    reps = []
    for c in clusters.values():
        # Representative: strongest front page, then richest headline.
        doc, page = max(c["docs"],
                        key=lambda dp: (front_weight(dp[1]),
                                        len((dp[0].get("headline") or {}).get("main") or "")))
        coverage = kw_freq[c["topic"]] if c["topic"] else 0
        reps.append((coverage, page, _story(doc, page, c["topic"], len(c["docs"]))))

    reps.sort(key=lambda r: (r[0], front_weight(r[1])), reverse=True)
    return [r[2] for r in reps[:4]]


def _rank_by_headline(docs):
    ranked = sorted((_story(d, as_int(d.get("print_page"))) for d in _candidate_docs(docs)),
                    key=lambda s: s["_richness"], reverse=True)
    chosen = []
    for s in ranked:
        if _too_similar(s["headline"], chosen):
            continue
        chosen.append(s)
        if len(chosen) == 4:
            break
    return chosen
