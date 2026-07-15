"""Iconicness ranker — selects the ~4 defining stories of a month.

Ported from the validated prototype/rank.py. Two modes:
  * topic clustering   (~1930+, where keyword coverage is rich)
  * headline richness  (pre-~1930 "keyword desert" fallback)
See PRD section 6.2 / 6.3.
"""
import re
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


LABEL_MIN = 6  # a short all-caps kicker seen this many times = a standing column


def _kicker(headline):
    """The leading label of a headline (text before the first ';'), uppercased."""
    if not headline:
        return ""
    seg = headline.split(";", 1)[0] if ";" in headline else headline
    return seg.strip().rstrip(".").strip().upper()


def _subhead(headline):
    """The descriptive text after the leading label, if any."""
    return headline.split(";", 1)[1].strip() if ";" in (headline or "") else ""


def label_kickers(docs):
    """Recurring short ALL-CAPS kickers that head standing columns rather than
    stories (e.g. "FROM WASHINGTON", "MARINE INTELLIGENCE", "TELEGRAMS")."""
    freq = Counter()
    for d in docs:
        h = (d.get("headline") or {}).get("main") or ""
        seg = (h.split(";", 1)[0] if ";" in h else h).strip().rstrip(".").strip()
        if (seg and len(seg.split()) <= 4 and seg.upper() == seg
                and any(c.isalpha() for c in seg)):
            freq[seg.upper()] += 1
    return {k for k, c in freq.items() if c >= LABEL_MIN}


def clean_label_headline(raw, labels):
    """If a headline leads with a recurring department label, drop it in favor
    of the descriptive subhead so the displayed headline is a real story."""
    if raw and _kicker(raw) in labels:
        sub = _subhead(raw)
        if len(sub) >= 12:
            return sub
    return raw


# "(2)"/"(3)" the NYT archive appends to disambiguate duplicate headlines — an
# artifact, not part of the headline. It rides on the kicker, so it can sit
# mid-headline ("ELLIS ISLAND(2); NEW...") as well as at the very end.
_DUP_MARK = re.compile(r"\(\d+\)(?=\s*(?:[;.]|$))")


def _story(doc, page, topic=None, cluster_size=1, headline=None):
    headline = headline or (doc.get("headline") or {}).get("main") or "(no headline)"
    headline = _DUP_MARK.sub("", headline)
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
        headline = ((d.get("headline") or {}).get("main") or "").strip()
        if not headline or "NO TITLE" in headline.upper():  # untitled filler
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
    labels = label_kickers(docs)  # standing-column headers to demote/clean

    if kw_ratio < KEYWORD_DESERT_THRESHOLD:
        stories = _rank_by_headline(docs, labels)
        mode = "headline-richness"
    else:
        stories = _rank_by_clusters(docs, kw_freq, n, labels)
        mode = "topic-clusters"
    return stories, {"mode": mode, "keyword_coverage": round(kw_ratio, 3)}


def _rank_by_clusters(docs, kw_freq, n, labels):
    # Front-page frequency per keyword — the clearest importance signal, since
    # editors put the month's biggest stories on page 1.
    fp_freq = Counter()
    for d in docs:
        if as_int(d.get("print_page")) == 1:
            for k in d.get("keywords") or []:
                if k.get("value"):
                    fp_freq[k["value"]] += 1

    def is_generic(k):
        # Hard stopwords are always noise. Otherwise a very common keyword is
        # only generic if it barely touches the front page; one that DOMINATES
        # page 1 is the month's lead (e.g. an election), so keep it — this is
        # what stops a niche book review out-ranking the real news.
        if k.lower() in STOP_KEYWORDS:
            return True
        return kw_freq[k] / n > GENERIC_DF and fp_freq[k] < 3

    clusters = {}
    for d in _candidate_docs(docs):
        page = as_int(d.get("print_page"))
        kws = [k.get("value") for k in (d.get("keywords") or []) if k.get("value")]
        specific = [k for k in kws if not is_generic(k)]
        # Topic = the article's keyword that most dominates the front page.
        topic = (max(specific, key=lambda v: (fp_freq[v], kw_freq[v]))
                 if specific else None)
        key = topic or f"_solo:{(d.get('headline') or {}).get('main')}"
        clusters.setdefault(key, {"docs": [], "topic": topic})["docs"].append((d, page))

    def raw_of(dp):
        return (dp[0].get("headline") or {}).get("main") or ""

    reps = []
    for c in clusters.values():
        # Representative: front page, then a real story over a standing-column
        # label, then richer headline.
        doc, page = max(c["docs"], key=lambda dp: (
            front_weight(dp[1]),
            0 if _kicker(raw_of(dp)) in labels else 1,
            len(raw_of(dp))))
        raw = (doc.get("headline") or {}).get("main") or ""
        rep_is_label = _kicker(raw) in labels
        topic = c["topic"]
        fp = fp_freq[topic] if topic else (1 if page == 1 else 0)
        cov = kw_freq[topic] if topic else 0
        story = _story(doc, page, topic, len(c["docs"]),
                       headline=clean_label_headline(raw, labels))
        # Rank by front-page presence, then real-story-over-label, then coverage,
        # then front weight, then headline richness (helps sparse old months).
        reps.append(((fp, 0 if rep_is_label else 1, cov,
                      front_weight(page), story["_richness"]), story))

    reps.sort(key=lambda r: r[0], reverse=True)
    return [r[1] for r in reps[:4]]


def find_event_story(docs, keyword_hook, labels=None):
    """Find the month's flagship story for a curated event by matching its
    headline against a "|"-separated keyword hook. Returns a story dict (same
    shape as rank_month's) or None if nothing recognizable matched.

    Prefers the most front-page, richest matching headline so a page-1 lead wins
    over a buried mention. Skips editorials/reviews/filler via _candidate_docs.
    """
    terms = [t.strip().lower() for t in (keyword_hook or "").split("|") if t.strip()]
    if not terms:
        return None
    if labels is None:
        labels = label_kickers(docs)

    best, best_key = None, None
    for d in _candidate_docs(docs):
        raw = (d.get("headline") or {}).get("main") or ""
        low = raw.lower()
        if not any(t in low for t in terms):
            continue
        page = as_int(d.get("print_page"))
        # A real story over a standing-column label, then front-page, then richer.
        key = (0 if _kicker(raw) in labels else 1,
               front_weight(page), headline_richness(raw, page), len(raw))
        if best_key is None or key > best_key:
            best, best_key = d, key
    if best is None:
        return None
    raw = (best.get("headline") or {}).get("main") or ""
    return _story(best, as_int(best.get("print_page")),
                  headline=clean_label_headline(raw, labels))


def _rank_by_headline(docs, labels):
    stories = []
    for d in _candidate_docs(docs):
        raw = (d.get("headline") or {}).get("main") or ""
        s = _story(d, as_int(d.get("print_page")),
                   headline=clean_label_headline(raw, labels))
        s["_is_label"] = _kicker(raw) in labels
        stories.append(s)
    # Real stories before standing-column labels, then by headline richness.
    stories.sort(key=lambda s: (0 if s["_is_label"] else 1, s["_richness"]),
                 reverse=True)
    chosen = []
    for s in stories:
        if _too_similar(s["headline"], chosen):
            continue
        chosen.append(s)
        if len(chosen) == 4:
            break
    return chosen
