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
import sys
from zoneinfo import ZoneInfo

from . import blurb, config, nyt, selection, summaries, wikimedia
from .ranker import rank_month

PUBLIC_STORY_KEYS = ("headline", "summary", "image", "image_source", "url")


def _clean_story(s):
    return {k: s.get(k) for k in PUBLIC_STORY_KEYS}


def card_image(story, year, with_wikimedia=True):
    """Best image for a story card: its NYT photo (recent era) if present, else a
    Wikimedia image of the topic/event (older eras). Rendered as a newsprint
    halftone on the client, so era/style never leaks. Returns (url, source)."""
    nyt = story.get("image")  # from ranker.pick_image (NYT), may be None
    if nyt:
        return nyt, "The New York Times"
    if not with_wikimedia:
        return None, None
    term = story.get("topic") or story["headline"].split(";")[0].strip()
    img = wikimedia.find_image(f"{term} {year}")
    return (img["url"], img["source"]) if img else (None, None)


def build_round(index, year, month, with_blurb=True):
    docs = nyt.fetch_month(year, month)
    stories, meta = rank_month(docs)
    if not stories:
        raise ValueError(f"{year}-{month:02d} produced no rankable stories")
    if with_blurb:
        # Clarify the cryptic abstracts into plain-English play-screen summaries.
        for s, clear in zip(stories, summaries.clarify(year, month, stories)):
            s["summary"] = clear
    text = blurb.generate(year, month, stories) if with_blurb else None
    # One image per story card (halftone-treated on the client).
    for s in stories:
        s["image"], s["image_source"] = card_image(s, year, with_wikimedia=with_blurb)
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
