// Times Search — game controller. Plain JS, no framework.
(function () {
  "use strict";

  // Default to today's ET date (Wordle-style rollover); ?date= overrides.
  // Falls back to a known edition if today's isn't published yet.
  const params = new URLSearchParams(location.search);
  const todayET = new Intl.DateTimeFormat("en-CA",
    { timeZone: "America/New_York" }).format(new Date());
  const FALLBACK_DATE = "2026-06-28";
  const DATE = params.get("date") || todayET;
  const MONTHS = ["", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

  const app = document.getElementById("app");
  const masthead = document.querySelector(".masthead");
  const scoreboard = document.getElementById("scoreboard");
  const roundPill = document.getElementById("round-pill");
  const scoreTotalEl = document.getElementById("score-total");

  const state = {
    puzzle: null, round: 0, results: [], total: 0,
    completed: false, submitted: false, daily: null,
  };

  // One game per day, no accounts: persist progress in localStorage keyed by
  // the puzzle date (Wordle-style). Per-device, clearable — fine for MVP.
  // Key by the actually-loaded puzzle date (may differ from DATE if we fell back).
  const storageKey = () => `times-search:v1:${state.puzzle ? state.puzzle.date : DATE}`;
  function saveProgress() {
    try {
      localStorage.setItem(storageKey(), JSON.stringify({
        round: state.round, results: state.results,
        total: state.total, completed: state.completed,
        submitted: state.submitted, daily: state.daily,
      }));
    } catch (_) { /* storage blocked (private mode); progress just won't persist */ }
  }
  function loadProgress() {
    try { return JSON.parse(localStorage.getItem(storageKey()) || "null"); }
    catch (_) { return null; }
  }

  // ---- helpers ----
  const escapeHtml = (s) => (s || "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Old NYT headlines are long, multi-deck run-ons. Collapse to a concise,
  // readable headline.
  function displayHeadline(raw) {
    if (!raw) return "(untitled)";
    let h = raw.replace(/\s+/g, " ").trim();
    const semi = h.indexOf(";");
    if (semi > 0 && /^\s*[A-Z][A-Z'’&.\-]+\s+[A-Z]/.test(h.slice(semi + 1))) {
      // A stack of ALL-CAPS decks ("HOUSE VOTES PEACE; SENATE AND HARDING…") —
      // keep only the first deck.
      h = h.slice(0, semi);
    } else {
      // A kicker + Title-Case subhead with trailing ALL-CAPS decks
      // ("…Esmeralda. WILSON BARRETT AS A ROMAN…") — drop the trailing decks.
      // Cut at a sentence break followed by 2+ caps words (not after "U.S.").
      const m = h.match(/[^A-Z][.;]\s+[A-Z][A-Z'’&.\-]+\s+[A-Z][A-Z'’&.\-]+/);
      if (m && m.index > 18) h = h.slice(0, m.index + 2).trim();
    }
    if (h.length > 92) h = h.slice(0, 90).replace(/[\s,;:.\-–—]+\S*$/, "") + "…";
    return h.replace(/[;,]\s*$/, "");
  }

  function setScoreboard() {
    masthead.hidden = false;
    scoreboard.hidden = false;
    roundPill.textContent = `Round ${state.round + 1} / ${state.puzzle.rounds.length}`;
    scoreTotalEl.textContent = state.total.toLocaleString();
  }

  // Animate a number counting up (eases out). Ends on the exact value.
  function countUp(el, to, prefix = "", dur = 650) {
    const start = performance.now();
    (function tick(now) {
      const t = Math.min((now - start) / dur, 1);
      el.textContent = prefix + Math.round(to * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(tick);
    })(start);
  }

  // ---- home screen ----
  function renderHome() {
    masthead.hidden = true;
    scoreboard.hidden = true;
    // CTA reflects whether you've already played today.
    const cta = state.completed
      ? { label: "See Your Results", action: renderResults }
      : state.results.length
        ? { label: "Resume Today’s Edition", action: renderPlay }
        : { label: "Play Today’s Edition", action: startGame };
    app.innerHTML = `
      <section class="screen home">
        <div class="home-nameplate">
          <div class="home-rule"></div>
          <h1 class="home-title">Times Search</h1>
          <p class="home-subtitle">a daily history game</p>
          <div class="home-rule"></div>
        </div>
        <ol class="howto">
          <li><span class="howto-n">1</span><span>Read the front page — four real New York Times stories, all from one month.</span></li>
          <li><span class="howto-n">2</span><span>Guess the <strong>month and year</strong> they ran.</span></li>
          <li><span class="howto-n">3</span><span>The closer you are, the higher your score. Three editions a day.</span></li>
        </ol>
        <button id="play" class="primary">${cta.label}</button>
        <details class="editors-note">
          <summary>Editor&rsquo;s Note</summary>
          <p>Every front page is a fingerprint of its moment. A country at war doesn&rsquo;t
          read like a country at peace. We give you four stories and want you to think:
          <em>when?</em> What is the feeling? Read and process to show your touch and
          understanding of history, and the lens we see it through.</p>
        </details>
      </section>`;
    document.getElementById("play").addEventListener("click", cta.action);
  }

  // ---- play screen ----
  function renderPlay() {
    const round = state.puzzle.rounds[state.round];
    setScoreboard();

    // Swipeable cards, one story each. Images are era-neutral halftones so they
    // never leak the date; the redacted dateline stays. PRD §6.7.
    const n = round.stories.length;
    const card = (s, i) => `
      <article class="card">
        ${s.image ? `<div class="card-media"><img class="halftone" src="${escapeHtml(s.image)}" alt="" loading="lazy" /></div>` : ""}
        <div class="card-body">
          <span class="card-index">${i + 1} / ${n}</span>
          <h2>${escapeHtml(displayHeadline(s.headline))}</h2>
          ${s.summary ? `<p>${escapeHtml(s.summary)}</p>` : ""}
        </div>
      </article>`;

    const paper = `
      <div class="paper-masthead standalone">
        <span class="paper-name">Times Search</span>
        <div class="paper-dateline">
          <span class="redacted">██████ ██, ████</span>
          <span class="redacted">No. ██,███</span>
        </div>
      </div>
      <p class="prompt">Swipe through all four. When did they run?</p>
      <div class="carousel">${round.stories.map(card).join("")}</div>`;

    const monthOpts = MONTHS.slice(1).map((m, i) =>
      `<option value="${i + 1}">${m}</option>`).join("");

    app.innerHTML = `
      <section class="screen play">
        ${paper}
        <form class="guess" id="guess-form" novalidate>
          <div class="guess-inner">
            <p class="error" id="guess-error" hidden></p>
            <div class="guess-row">
              <label class="gf">Month
                <select id="month" required>
                  <option value="" selected disabled>—</option>${monthOpts}
                </select>
              </label>
              <label class="gf">Year
                <input id="year" type="number" inputmode="numeric"
                       min="1851" max="2019" placeholder="1851–2019" required />
              </label>
              <button type="submit" class="primary guess-submit">Go to Press</button>
            </div>
          </div>
        </form>
      </section>`;

    document.getElementById("guess-form").addEventListener("submit", onSubmit);
  }

  function onSubmit(e) {
    e.preventDefault();
    const month = parseInt(document.getElementById("month").value, 10);
    const year = parseInt(document.getElementById("year").value, 10);
    const err = document.getElementById("guess-error");
    if (!month || !year || year < 1851 || year > 2019) {
      err.textContent = "Pick a month and a year between 1851 and 2019.";
      err.hidden = false;
      return;
    }
    const round = state.puzzle.rounds[state.round];
    const guess = { year, month };
    const e_months = Scoring.errorMonths(guess, round.answer);
    const points = Scoring.roundPoints(e_months);
    state.total += points;
    state.results.push({ guess, actual: round.answer, err: e_months, points });
    saveProgress();
    renderReveal();
  }

  // ---- reveal screen ----
  function renderReveal() {
    const round = state.puzzle.rounds[state.round];
    const r = state.results[state.round];
    setScoreboard();
    const last = state.round === state.puzzle.rounds.length - 1;

    const links = round.stories.map((s) =>
      `<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">
        ${escapeHtml(displayHeadline(s.headline))}</a></li>`).join("");

    // "How far off" timeline: your guess vs the real year on an 1851–2019 line.
    const MINY = 1851, MAXY = 2019;
    const pos = (y) => Math.max(0, Math.min(100, ((y - MINY) / (MAXY - MINY)) * 100));
    const gp = pos(r.guess.year), ap = pos(round.answer.year);
    const lo = Math.min(gp, ap), hi = Math.max(gp, ap);
    const timeline = `
      <div class="timeline">
        <div class="tl-track">
          <div class="tl-gap" style="left:${lo}%;width:${hi - lo}%"></div>
          <div class="tl-dot guess" style="left:${gp}%"></div>
          <div class="tl-dot actual" style="left:${ap}%"></div>
        </div>
        <div class="tl-ends"><span>1851</span><span>${MAXY}</span></div>
        <div class="tl-key">
          <span class="k guess">Your guess (${r.guess.year})</span>
          <span class="k actual">Actual (${round.answer.year})</span>
        </div>
      </div>`;

    // Reveal-screen image: NYT photo (recent era) or Wikimedia (older era).
    const ri = round.reveal_image;
    const imageBlock = ri && ri.url ? `
      <figure class="reveal-figure">
        <img class="reveal-image" src="${escapeHtml(ri.url)}" alt="" loading="lazy" />
        <figcaption>Image: ${escapeHtml(ri.source || "")}${
          ri.title ? ` — ${escapeHtml(ri.title)}` : ""}</figcaption>
      </figure>` : "";

    app.innerHTML = `
      <section class="screen reveal">
        <p class="reveal-eyebrow">These stories ran in&hellip;</p>
        <p class="reveal-date stamp">${MONTHS[round.answer.month]} ${round.answer.year}</p>
        <p class="reveal-verdict">
          <span class="verdict-icon">${Scoring.eraIcon(r.err)}</span>
          <span class="verdict-main">${Scoring.errorLabel(r.err)}</span>
          <span class="verdict-tone">${Scoring.toneMessage(r.err)}</span>
          <span class="verdict-points" id="vpoints">+0</span>
        </p>
        ${timeline}
        ${round.blurb ? `<p class="blurb">${escapeHtml(round.blurb)}</p>` : ""}
        ${imageBlock}
        <details class="sources" open>
          <summary>The stories</summary>
          <ul class="links">${links}</ul>
        </details>
        <button id="next" class="primary">${last ? "The Final Word" : "Next Edition"}</button>
      </section>`;

    countUp(document.getElementById("vpoints"), r.points, "+");
    document.getElementById("next").addEventListener("click", () => {
      if (last) { renderResults(); } else { state.round += 1; renderPlay(); }
    });
  }

  // ---- results screen ----
  // Real placement comes from /api/score. Until it responds (or if the backend
  // isn't reachable), we show a local estimate so the screen is instant.
  const SYNTH_DIST = [2, 5, 9, 14, 18, 19, 15, 10, 6, 2];
  const scoreBucket = (total) => Math.min(9, Math.floor(total / (Scoring.maxTotal / 10)));

  function estimate(total) {
    const sum = SYNTH_DIST.reduce((a, b) => a + b, 0);
    let below = 0;
    for (let i = 0; i < scoreBucket(total); i++) below += SYNTH_DIST[i];
    return { topPct: Math.max(1, 100 - Math.round(below / sum * 100)), dist: SYNTH_DIST, count: null };
  }

  let submitting = false;
  async function submitScore() {
    if (state.submitted || submitting) return;
    submitting = true;
    try {
      const res = await fetch("/api/score", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: state.puzzle.date, score: state.total }),
      });
      if (res.ok) {
        const j = await res.json();
        if (j && j.topPct != null && Array.isArray(j.dist)) {
          state.submitted = true;
          state.daily = { topPct: j.topPct, count: j.count, dist: j.dist };
          saveProgress();
          renderResults(); // re-render with the real numbers
        }
      }
    } catch (_) { /* keep the estimate */ } finally { submitting = false; }
  }

  function placementLine(d) {
    if (d.count == null) return `You placed in the <strong>top ${d.topPct}%</strong> today`;
    if (d.count <= 1) return `You&rsquo;re the <strong>first</strong> to finish today!`;
    return `Top <strong>${d.topPct}%</strong> of <strong>${d.count.toLocaleString()}</strong> players today`;
  }

  function renderResults() {
    masthead.hidden = true;
    scoreboard.hidden = true;
    saveProgress();
    const data = state.daily || estimate(state.total);
    const bucket = scoreBucket(state.total);
    const max = Math.max(...data.dist, 1);

    const bars = data.dist.map((c, i) => `
      <div class="bar ${i === bucket ? "you" : ""}"
           style="height:${Math.max(3, Math.round((c / max) * 100))}%"></div>`).join("");

    const recap = state.puzzle.rounds.map((round, i) => {
      const r = state.results[i];
      return `<li>
        <span class="recap-square">${Scoring.shareSquare(r.err)}</span>
        <span class="recap-date">${MONTHS[round.answer.month]} ${round.answer.year}</span>
        <a class="recap-link" href="${escapeHtml(round.stories[0].url)}"
           target="_blank" rel="noopener">${escapeHtml(displayHeadline(round.stories[0].headline))}</a>
      </li>`;
    }).join("");

    app.innerHTML = `
      <section class="screen results">
        <h2>That&rsquo;s the edition.</h2>
        <p class="final-score"><strong id="ftotal">0</strong>
          <span>/ ${Scoring.maxTotal.toLocaleString()}</span></p>
        <p class="percentile">${placementLine(data)}</p>
        <div class="histogram">${bars}</div>
        <h3>Today&rsquo;s front pages, revealed</h3>
        <ul class="recap">${recap}</ul>
        <div class="results-actions">
          <button id="share" class="primary big-share">Share your score</button>
          <button id="home" class="home-link">&larr; Home</button>
        </div>
        <p class="toast" id="toast" hidden></p>
      </section>`;

    countUp(document.getElementById("ftotal"), state.total, "", 850);
    document.getElementById("home").addEventListener("click", renderHome);
    document.getElementById("share").addEventListener("click", share);
    if (!state.submitted) submitScore();
  }

  // Adapts to whatever domain the game is served from (vercel.app or custom).
  const SHARE_URL = location.origin + "/";

  function shareText() {
    const squares = state.results.map((r) => Scoring.shareSquare(r.err)).join("");
    return `Times Search — ${state.puzzle.date}\n${squares}  ` +
      `${state.total.toLocaleString()}/${Scoring.maxTotal.toLocaleString()}`;
  }

  async function share() {
    const text = shareText();
    const fullText = `${text}\n${SHARE_URL}`;
    try {
      if (navigator.share) {
        // Pass the URL as part of `text` rather than as a separate `url` field:
        // macOS Safari's share sheet (Mail, Messages, Notes) drops `text` and
        // shows only the URL when both fields are given, unlike iOS Safari.
        await navigator.share({ title: "Times Search", text: fullText });
        return;
      }
      await navigator.clipboard.writeText(fullText);
      toast("Copied — score and link on your clipboard!");
    } catch (_) { toast("Couldn't share — here it is:\n" + text + "\n" + SHARE_URL); }
  }

  function toast(msg) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = msg; t.hidden = false;
    setTimeout(() => { t.hidden = true; }, 2500);
  }

  function startGame() {
    if (state.completed) { renderResults(); return; } // no replay once done
    state.round = 0; state.results = []; state.total = 0;
    renderPlay();
  }

  // Restore any saved progress for today, then show the right screen.
  function restoreAndRoute() {
    const saved = loadProgress();
    if (saved && Array.isArray(saved.results)) {
      state.results = saved.results;
      state.total = saved.total || 0;
      state.completed = !!saved.completed ||
        saved.results.length >= state.puzzle.rounds.length;
      state.submitted = !!saved.submitted;
      state.daily = saved.daily || null;
      state.round = state.completed
        ? state.puzzle.rounds.length - 1
        : saved.results.length;
    }
    if (state.completed) renderResults();
    else if (state.results.length) renderPlay(); // resume mid-game
    else renderHome();
  }

  async function fetchPuzzle(d) {
    const res = await fetch(`puzzles/${d}.json`, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  // ---- boot ----
  async function init() {
    app.innerHTML = `<section class="screen loading"><p>Setting the type&hellip;</p></section>`;
    try {
      try {
        state.puzzle = await fetchPuzzle(DATE);
      } catch (e) {
        if (params.get("date")) throw e;           // explicit date: don't mask
        state.puzzle = await fetchPuzzle(FALLBACK_DATE); // today's not out yet
      }
      restoreAndRoute();
    } catch (e) {
      app.innerHTML = `<section class="screen error">
        <h2>No edition available</h2>
        <p class="hint">Today&rsquo;s puzzle hasn&rsquo;t been published yet. Check back soon.</p>
      </section>`;
    }
  }

  init();
})();
