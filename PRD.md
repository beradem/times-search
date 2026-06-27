# Times Search — Product Requirements Document

**Status:** Draft v0.1 (working draft — sections marked `OPEN` are unresolved and meant to be decided together)
**Last updated:** 2026-06-27
**Author:** Bera Demirbilek (with Claude)

---

## 1. Summary

**Times Search** is a daily web game in the spirit of Wordle. Each day, a player is shown three rounds of historical New York Times front-page stories — four major headlines per round, drawn from a single real month somewhere between 1851 and 2019 — and must guess the **month and year** the stories are from. The closer the guess, the higher the score. After three rounds, the player gets a total score, sees how they ranked against everyone who played that day, and can share a spoiler-free result card.

The hook: the NYT archive is a 170-year record of "what the world was paying attention to." Times Search turns that into a daily test of historical intuition.

### One-liner
> Guess the month and year four real NYT headlines are from. Three rounds a day.

---

## 2. Goals & Non-Goals

### Goals
- Create a **daily habit loop** (play once per day, come back tomorrow).
- Make history feel **intuitive and guessable** through real primary sources, not trivia.
- Ship a **lean v1** that is solo-play + shareable, with a minimal backend only for the daily score distribution.
- Generate puzzles **fully algorithmically** from the Archive API so the game can run daily without manual curation.

### Platform & longer-term vision
- **v1: responsive web** (Wordle-style — fast to ship, instantly shareable, no install).
- **North star: a native iOS App Store app** once the game proves good. This doesn't change v1, but it informs architecture: keep **game/scoring/puzzle logic portable** (decoupled from web-only UI) so it can be reused by a native client, and note that the iOS version will likely justify **accounts + Game Center-style leaderboards** (which in turn would revisit the §8 client-side-answers decision).

### Non-Goals (v1)
- User accounts, login, profiles, streak tracking.
- Real-time multiplayer or head-to-head.
- A full leaderboard with named players (we only show anonymous percentile + distribution).
- Native mobile apps (v1 is responsive web; native iOS is the *eventual* goal — see above).
- Content beyond the NYT Archive API.

### Success metrics *(proposed — revisit; see note)*
This is a daily-habit game, so the honest north star is **"do people come back."**
- **Primary: D7 retention** — of players who play once, what share return within 7 days. The single best signal that the loop works.
- **Secondary: share rate** (% of completed games that tap Share) — the main organic growth lever for a Wordle-like game.
- **Health checks:** completion rate (% of starts finishing all 3 rounds) and median score trend (are puzzles satisfying, not punishing?).

*Note: metrics are hard to commit to pre-launch. Reasonable to defer a firm target and just instrument all four, then set a D7 goal once we see a baseline.*

---

## 3. Target User & Core Insight

**Who:** The Wordle / Connections / Worldle daily-puzzle crowd — people who like a quick, shareable, once-a-day brain game. Secondary: history buffs, news junkies, students.

**Core insight:** People can't recite dates, but they *can* reason from context — "TV is being discussed as new… no internet… Cold War tone… this feels late '50s." Real headlines reward that reasoning in a way trivia questions don't. The guessing is **deductive, not recall-based**, which makes it accessible to non-experts.

---

## 4. Core Gameplay Loop

A daily game = **3 rounds**. Every player gets the **same 3 rounds** on a given calendar day (deterministic daily puzzle, Wordle-style).

### Per round
1. **Prompt screen** ("In the Times last month…")
   - 4 headlines, each with a 1–2 sentence summary (from the article `abstract`/`snippet`).
   - 1 primary image; optionally a 2nd image. *(images only when available — see §6 degradation)*
   - Inputs: **Month** (dropdown/picker, Jan–Dec) and **Year** (input, 1851–2019).
   - **Submit Guess** button.
2. **Reveal screen**
   - Shows the true **Month + Year**.
   - "**You were X months off**" + a tone message (see §5.3).
   - Running **Score** (top-right, accumulates across rounds).
   - A longer "this month in history" blurb + links to the real NYT articles + another image.
   - **Next Round** (rounds 1–2) / **See Final Score** (round 3).
3. Repeat for 3 rounds.

### End of game — Results screen
- **"You were in the top XX% of players today."**
- A **score-distribution histogram** with the player's bucket highlighted.
- **Recap** of all 3 rounds: the real MM/YYYY + story thumbnails.
- **Home** and **Share** buttons.

### Rules
- **One game per day** per device (enforced client-side via localStorage in v1; not account-locked).
- Puzzle rolls over at **midnight America/New_York (ET)** every night, globally (same puzzle for everyone, Wordle-style). See §6.4.
- No mid-game retries; each guess is final on submit.

---

## 5. Scoring Model

> Decision: **months-off with decaying points.**

### 5.1 Error metric
Convert each date to an absolute month index:

```
index(year, month) = year * 12 + (month - 1)
error_months = | index(guess) - index(actual) |
```

So "right year, wrong month by 2" = error of 2; "one year too early, same month" = error of 12.

### 5.2 Points per round *(proposed — constants are tunable)*
Exponential decay so exact answers feel great and the falloff is forgiving early, harsh later:

```
round_points = round( MAX_POINTS * 0.5 ^ (error_months / HALF_LIFE) )
```

With `MAX_POINTS = 1000` and `HALF_LIFE = 18` months:

| error (months) | points |
|---|---|
| 0 (exact)      | 1000 |
| 3              | ~891 |
| 6              | ~794 |
| 12 (1 yr)      | ~630 |
| 18             | 500 |
| 36 (3 yr)      | 250 |
| 60 (5 yr)      | ~99 |
| 120 (10 yr)    | ~10 |

- **Max daily score = 3000** (3 × 1000).
- Asymptotic to 0; no hard cutoff (a wild guess still scores a few points, which feels less punishing).

**OPEN / to tune together:**
- Is 18-month half-life the right "feel"? (Smaller = harsher, rewards precision; larger = forgiving.)
- Given the **full 1851–2019 range**, should `HALF_LIFE` scale with era difficulty (older = more forgiving, since cues are subtler)? Or keep one constant for simplicity and let v1 data tell us?
- Bonus for an exact-month hit? Streak bonus across rounds within a day?

### 5.3 Tone messages (on reveal)
| error_months | message |
|---|---|
| 0 | "Bullseye." |
| 1–3 | "So close!" |
| 4–12 | "Close." |
| 13–36 | "Nice try." |
| 37+ | "Way off." |

*(copy is placeholder — final voice TBD)*

---

## 6. Content & Puzzle Generation

> Decision: **fully algorithmic**, optimizing to surface the **biggest / most iconic stories** of the chosen month, no human in the loop.

This is the hardest part of the product. The Archive API returns *every* article for a month (~20MB, thousands of docs) with no built-in "importance" ranking. We must define one.

### 6.1 Pipeline (offline, pre-generated — never call the 20MB endpoint from the browser)
1. **Pick a target month/year** for each of the 3 daily rounds (selection strategy in §6.4).
2. **Fetch** `/{year}/{month}.json` once; cache the raw JSON.
3. **Filter to "real news"**: keep `document_type == "article"`; **blocklist** unwanted `type_of_material` (Op-Ed, Editorial, Review, Letter, Correction, Obituary, Caption, etc.). *Note: do NOT allowlist "News" — older archives label real articles literally as "Article", so an allowlist filters out the entire month.*
4. **Score each article for "iconicness"** (§6.2).
5. **Cluster by topic and pick the top 4 clusters**, taking each cluster's **best front-page representative** so we show four *distinct* events, each represented by its strongest article (not a tangential one).
6. **Build the puzzle record**: 4 headlines + abstracts, 1–2 image URLs, the "this month in history" blurb, article links, and the answer date.
7. **Store** as a static daily puzzle (JSON in a CDN/store), keyed by calendar date.

### 6.2 "Iconicness" ranking heuristic *(validated against real data — see `prototype/rank.py`)*

The defining signal is **topic-cluster size**: how many articles the month devoted to one specific subject. Apollo 11 = a 340-article cluster in July 1969; the bank holiday = a 571-article cluster in March 1933. This is the closest proxy the API gives us to "what the world was paying attention to." Implementation:

1. **Build month-wide keyword frequency.**
2. **Strip generic keywords.** Any keyword tagged on **>5% of the month's docs** (e.g. `ASTRONAUTICS`, `UNITED STATES PROJECTS`) plus a hardcoded stoplist (`United States`, `New York City`, `Deaths`, `Editorials`, `Politics and Government`, …) is boilerplate, not a topic. *Without this filter, a routine tax vote tagged `United States` (1,395 hits) outranks the moon landing.*
3. **Topic = each article's most-frequent *specific* keyword.** Cluster articles by topic.
4. **Rank clusters by size** (≈ coverage volume).
5. **Representative per cluster** = the article with the strongest front-page placement, tie-broken by **headline richness** (long multi-deck headlines = the lead story).

Secondary tie-break signals: `print_page == 1`/`print_section == "A"` (the editors' own ranking) and presence of `multimedia` (for the UI).

**Dead signals discovered in prototyping:**
- `word_count` is **always 0** in Archive API responses (it's populated only in the *Article Search* API). Removed from the model.
- `news_desk` / `section_name` are frequently `null` even in 1969. Usable as a weak bonus, not a primary signal.

### 6.3 Degradation across eras (the *1930*, not 1851, problem)
Prototyping corrected our assumption. The cliff is **keyword availability**, and it falls in the **late 1920s**, not 1900:

| Era | Keyword coverage (measured) | Heuristic quality |
|---|---|---|
| ~1930–2019 | 58–69% of articles tagged | **Works well** — clustering surfaces the iconic stories (verified: 1933 bank holiday, 1945 V-J Day, 1969 Apollo 11). |
| pre-~1930 | ~**0%** (1921 = 8 of 8,591) | **Collapses** to front-page + headline-length only; can't rank by importance. |

**Fallback for the keyword desert (pre-~1930) — DECIDED: built & validated.** When a month's keyword coverage is below `KEYWORD_DESERT_THRESHOLD` (10%), the ranker switches to a **headline-richness** heuristic: pre-keyword NYT set lead stories in long, multi-deck, ALL-CAPS headlines while filler ran short one-liners. Score = `0.40·front-page + 0.25·length + 0.20·deck-count + 0.15·caps-ratio`, with same-event front-pagers de-duped by significant-word (Jaccard) overlap since there are no topics to cluster on.
- *Validated:* July 1921 now surfaces the **Dempsey–Carpentier fight** and the **Irish truce** (real lead stories) instead of trivia.

**Implications & remaining refinement:**
- The UI must handle **0 images** gracefully (older articles have no `multimedia`); the wireframe already treats images as optional. Confirm the prompt screen works text-only.
- **Partial-keyword era (~1900–1930, 30–50% coverage):** cluster mode catches the *top* story (April 1912 correctly leads with the **Titanic**) but the tail gets noisy from mis-tagged small clusters. **Refinement (later):** blend headline-richness into cluster ranking so weak-headline clusters lose. Tracked, not yet built.

### 6.4 Daily / round selection strategy *(DECIDED)*

Each day's game = **3 rounds, each a random MM/YYYY pair** drawn from the full archive (random year 1851–2019 × random month 1–12). Pure random — no era-weighting or difficulty curve in v1.

**Rules:**
- The **3 pairs within a day must be distinct** from each other.
- **No MM/YYYY pair may repeat within a rolling 14-day (2-calendar-week) window** — i.e. today's 3 pairs must not collide with any of the previous 13 days' picks (42 pairs total in the window). Trivially satisfiable: 2,028 possible pairs vs. 42 in flight.
- **Rollover: midnight America/New_York (ET) every night**, Wordle-style. (Also resolves §4's rollover question.)

**Determinism (critical):** because the game is Wordle-style — everyone plays the *same* 3 rounds and we show a daily score distribution — selection must be **deterministic / precomputed per date, not per-user random**. Approach:
- Seed an RNG with the ET calendar date (e.g. `2026-06-27`).
- Draw 3 distinct pairs; reject any pair already used in the prior 13 days (the pre-generation job stores each day's selection and reads back the window).
- Persist the day's selection alongside the generated puzzle.

**Quality guard (recommended):** before committing a drawn pair, run it through the §6.2 ranker and **reject months that can't yield 4 distinct, rankable stories** (re-draw instead). This keeps pure-random selection from occasionally serving a thin/unviable month, without biasing the era distribution. *(Flagging — confirms with the "pure random" intent; it only filters genuinely broken months, not "boring" ones.)*

### 6.5 The "this month in history" blurb *(DECIDED: LLM-generated via Groq)*

The reveal-screen blurb is **LLM-generated using a Groq API key** (Groq serves fast, cheap open models — e.g. Llama — well-suited to batch generation). It runs **in the pre-generation pipeline, not at play time**, so each blurb is produced once per puzzle and is cheap, cacheable, and reviewable.

**Anti-hallucination grounding (important):** the blurb describes a *real* month in history, so the model must be **grounded in the 4 extracted top stories** — pass their headlines + abstracts as context and instruct the model to summarize *only* what those articles support, not to volunteer outside "facts." This keeps invented dates/events out. *(Optional later: a lightweight factual spot-check or human review pass before publish.)*

### 6.6 Legal / ToS
- **Resolved:** project is **non-commercial, for social learning**, so NYT content-display terms are not considered a blocker for this use.
- Still good practice: respect API rate limits (per-minute and per-day 429s) via pre-generation/caching, and attribute the NYT as the source in the UI.

---

## 7. Results, Sharing & Social (v1)

> Decision: **solo + shareable, no accounts.** A minimal backend exists *only* to compute the daily distribution.

### 7.1 Percentile + histogram
- On game completion, the client **POSTs the total score** (anonymous, with the puzzle date) to a backend.
- Backend keeps a **per-day score distribution** (e.g. a histogram of buckets) and returns the player's percentile + the bucket counts to render the chart.
- No identity, no persistence beyond the daily aggregate. *(OPEN — anti-cheat: someone could spam scores. For v1, accept it; it only skews an anonymous stat.)*

### 7.2 Share card
- Wordle-style, **spoiler-free**: shows the 3 rounds as a compact visual (e.g. emoji/blocks encoding how close each guess was), the total score, and the date — **never the answers**.
- Copies text + a link to the site. *(OPEN — image card vs. text-only; text is simpler and travels better.)*

### 7.3 Deferred to later (explicitly out of v1)
- Accounts, streaks, history calendar, named leaderboards, friend challenges.

---

## 8. Data & Technical Architecture (high level)

- **Puzzle pre-generation job** (scheduled): runs the §6 pipeline ahead of time, produces static daily-puzzle JSON. Decouples gameplay from the slow 20MB API and respects rate limits.
- **Puzzle store/CDN:** serves the day's puzzle to clients as small JSON — headlines, abstracts, image URLs, links, the blurb, **and the answers**. *(DECIDED: **client-side answers**, Wordle-style. Cheating only fools yourself; the shared "top XX%" stat is already spam-gameable with no accounts. Revisit if the future iOS app adds accounts/competitive leaderboards. See §10.)*
- **Score-distribution service:** tiny endpoint storing daily anonymous scores + returning percentile/histogram.
- **Client:** responsive web app implementing the 4 screens.

*(OPEN — concrete stack TBD: static site + serverless functions is likely enough.)*

---

## 9. Scope: v1 vs. Later

### v1 (launch)
- 3-round daily game, full loop across all 4 screens.
- Algorithmic puzzle generation, pre-generated daily.
- Months-off decaying-points scoring.
- Solo play, one game/day per device.
- Anonymous percentile + distribution.
- Spoiler-free share.
- Full 1851–2019 guess range; 3 random pairs/day, no repeat in a rolling 14 days, deterministic per ET date (§6.4).
- LLM-generated "this month in history" blurb via Groq (§6.5).
- Client-side answers, Wordle-style (§8).
- Responsive web.

### Later (backlog)
- **Native iOS App Store app** (the longer-term goal — §2), likely with accounts + Game Center leaderboards.
- Accounts, streaks, history.
- Difficulty modes / era-specific challenges.
- Archive/practice mode (play past days).
- Hints (reveal a section name, a decade nudge) — *possibly with a scoring penalty*.
- Richer share image card.
- Blend headline-richness into cluster ranking for the noisy partial-keyword era (~1900–1930) (§6.3).

---

## 10. Open Questions & Risks (consolidated)

1. ~~NYT ToS~~ — **resolved**: non-commercial / social-learning use, not a blocker. (§6.6)
2. ~~Pre-~1930 keyword desert~~ — **resolved**: built & validated a headline-richness fallback (§6.3). Remaining refinement: blend richness into cluster ranking for the noisy partial-keyword era (~1900–1930).
3. **Scoring feel** — half-life value; era-scaled difficulty; bonuses. (§5.2) *(scoring approach locked; constants tunable)*
4. ~~Daily/round selection & rollover~~ — **resolved**: 3 random MM/YYYY pairs/day, no repeat in a rolling 14 days, deterministic per ET date, midnight-ET rollover. (§6.4)
5. ~~Blurb generation~~ — **resolved**: LLM-generated via Groq, grounded in the 4 extracted stories. (§6.5)
6. ~~Answer trust~~ — **resolved**: client-side answers, Wordle-style; revisit for the iOS app. (§8)
7. ~~Platform~~ — **resolved**: responsive web v1; native iOS App Store app is the longer-term goal. (§2)
8. ~~Success metrics~~ — **resolved (proposed)**: D7 retention primary, share rate secondary; instrument all four, set a target post-launch. (§2)
9. **Scoring constants** — tune `HALF_LIFE` once we have playtest data (the only remaining substantive open item). (§5.2)

---

## Appendix A — API reference (from `archive-product.yaml`)

- Endpoint: `GET https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key=KEY`
- Range: **1851–2019**, month 1–12.
- Response: `response.docs[]` (Article). ~20MB, thousands of docs. **Not** browser-callable.
- Useful Article fields: `headline.main`, `abstract`/`snippet`, `pub_date`, `news_desk`, `section_name`, `print_page`, `print_section`, `word_count`, `type_of_material`, `document_type`, `keywords[].value`, `multimedia[].url`, `web_url`.
- Errors: `401` (bad key), `429` (rate limit — per-minute and per-day).
