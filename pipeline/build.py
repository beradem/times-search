"""Build a daily puzzle: selection -> ranker -> Groq blurb -> puzzle JSON.

Usage:
    python3 -m pipeline.build                       # today's ET date
    python3 -m pipeline.build 2026-07-01            # a specific date
    python3 -m pipeline.build --pairs 1969-7,1945-8,1933-3   # fixed pairs (test)
    python3 -m pipeline.build --no-blurb            # skip Groq (faster offline test)
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

from . import blurb, config, nyt, selection, summaries, wikimedia
from .ranker import rank_month

PUBLIC_STORY_KEYS = ("headline", "summary", "image", "image_source", "url")


def _clean_story(s):
    return {k: s.get(k) for k in PUBLIC_STORY_KEYS}


def _sig_words(text):
    cleaned = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    return {w for w in cleaned.split()
            if len(w) > 3 and any(c.isalpha() for c in w)}


def _relevant(query, title):
    """Does the page title share a real word with the query? Prefix-matches so
    plurals/variants count (election/elections, riot/riots)."""
    qs, ts = _sig_words(query), _sig_words(title)
    for a in qs:
        for b in ts:
            if a == b or (len(a) >= 4 and len(b) >= 4
                          and (a.startswith(b) or b.startswith(a))):
                return True
    return False


def _candidates(story):
    """Ordered (url, source, relevant) image candidates for one story: specific
    Wikipedia + Commons first, then the broad theme. Deduped by url."""
    specific = (story.get("_image_query") or story.get("topic")
                or story["headline"].split(";")[0].strip())
    broad = story.get("_image_query_broad") or story.get("topic") or ""
    out, seen = [], set()

    def add(items, query, force_relevant=False):
        for c in items:
            u = c.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            out.append((u, c["source"], force_relevant or _relevant(query, c.get("title"))))

    if specific:
        add(wikimedia.find_images(specific), specific)
        add(wikimedia.commons_images(specific), specific)  # variety for same-event dedup
    if broad and broad.lower() != (specific or "").lower():
        add(wikimedia.find_images(broad), broad, force_relevant=True)
    return out


def resolve_card_images(stories, year, with_wikimedia=True):
    """Assign one image per story, de-duplicated within the round and kept
    topical: NYT photo (recent) else the best relevant, unused candidate."""
    used = set()
    for s in stories:
        nyt = s.get("image")  # from ranker.pick_image (NYT), may be None
        if nyt:
            s["image"], s["image_source"] = nyt, "The New York Times"
            used.add(nyt)
            continue
        if not with_wikimedia:
            s["image"], s["image_source"] = None, None
            continue
        cands = _candidates(s)
        chosen = (next(((u, src) for u, src, rel in cands if rel and u not in used), None)
                  or next(((u, src) for u, src, rel in cands if u not in used), None)
                  or next(((u, src) for u, src, rel in cands if rel), None))
        if chosen:
            s["image"], s["image_source"] = chosen
            used.add(chosen[0])
        else:
            s["image"], s["image_source"] = None, None


def build_round(index, year, month, with_blurb=True):
    docs = nyt.fetch_month(year, month)
    stories, meta = rank_month(docs)
    if not stories:
        raise ValueError(f"{year}-{month:02d} produced no rankable stories")
    if with_blurb:
        # Clarify summaries and get targeted + broad image queries per story.
        for s, e in zip(stories, summaries.clarify(year, month, stories)):
            s["summary"] = e["summary"]
            s["_image_query"] = e["image_query"]
            s["_image_query_broad"] = e.get("image_query_broad", "")
    text = blurb.generate(year, month, stories) if with_blurb else None
    # One image per story card, de-duplicated within the round.
    resolve_card_images(stories, year, with_wikimedia=with_blurb)
    lead = stories[0]
    reveal = ({"url": lead["image"], "source": lead["image_source"]}
              if lead.get("image") else None)
    imgs = sum(1 for s in stories if s.get("image"))
    print(f"  round {index}: {year}-{month:02d}  [{meta['mode']}, "
          f"kw={meta['keyword_coverage']:.0%}]  -> {stories[0]['headline'][:50]}"
          f"  | imgs {imgs}/{len(stories)}", file=sys.stderr)
    return {
        "round": index,
        "answer": {"year": year, "month": month},
        "stories": [_clean_story(s) for s in stories],
        "reveal_image": reveal,
        "blurb": text,
        "ranking": meta,
    }


def today_et():
    return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", help="ET date YYYY-MM-DD (default: today ET)")
    ap.add_argument("--pairs", help="comma-separated YYYY-M pairs, bypasses selection")
    ap.add_argument("--no-blurb", action="store_true", help="skip Groq blurb")
    ap.add_argument("--no-record", action="store_true", help="don't write the ledger")
    args = ap.parse_args()

    date_str = args.date or today_et()

    if args.pairs:
        pairs = [tuple(int(x) for x in p.split("-")) for p in args.pairs.split(",")]
        record = False
    else:
        pairs = selection.select_pairs(date_str)
        record = not args.no_record

    print(f"Building puzzle for {date_str}: "
          f"{', '.join(f'{y}-{m:02d}' for y, m in pairs)}", file=sys.stderr)

    rounds = [build_round(i, y, m, with_blurb=not args.no_blurb)
              for i, (y, m) in enumerate(pairs, 1)]
    puzzle = {
        "date": date_str,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rounds": rounds,
    }

    os.makedirs(config.PUZZLE_DIR, exist_ok=True)
    out = os.path.join(config.PUZZLE_DIR, f"{date_str}.json")
    with open(out, "w") as f:
        json.dump(puzzle, f, indent=2, ensure_ascii=False)
    if record:
        selection.record(date_str, pairs)
    print(f"\nWrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
