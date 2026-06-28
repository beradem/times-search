// Times Search — game controller. Plain JS, no framework.
(function () {
  "use strict";

  // Pick the puzzle by ?date=YYYY-MM-DD (default: the sample).
  // In production this will default to today's ET date.
  const DATE = new URLSearchParams(location.search).get("date") || "2026-06-28";
  const PUZZLE_URL = `../puzzles/${DATE}.json`;
  const MONTHS = ["", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

  const app = document.getElementById("app");
  const scoreboard = document.getElementById("scoreboard");
  const roundPill = document.getElementById("round-pill");
  const scoreTotalEl = document.getElementById("score-total");

  const state = { puzzle: null, round: 0, results: [], total: 0 };

  // ---- helpers ----
  const escapeHtml = (s) => (s || "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Old headline.main is a long, multi-deck run-on (sometimes kicker-first).
  // Show a concise display headline. (Proper fix tracked in PRD backlog.)
  function displayHeadline(raw) {
    if (!raw) return "(untitled)";
    const parts = raw.split(";").map((s) => s.trim()).filter(Boolean);
    let h = parts[0] || raw;
    if (h.length < 25 && parts[1]) h += "; " + parts[1];
    return h.length > 110 ? h.slice(0, 107).trimEnd() + "…" : h;
  }

  function setScoreboard() {
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
    scoreboard.hidden = true;
    app.innerHTML = `
      <section class="screen home">
        <div class="home-nameplate">
          <div class="home-rule"></div>
          <h1 class="home-title">Times Search</h1>
          <p class="home-subtitle">a daily history game</p>
          <div class="home-rule"></div>
        </div>
        <p class="home-tagline">Four real front-page stories from a single month, somewhere since 1851. Name it.</p>
        <ol class="howto">
          <li><span class="howto-n">1</span><span>Read the front page — four real New York Times stories, all from one month.</span></li>
          <li><span class="howto-n">2</span><span>Guess the <strong>month and year</strong> they ran.</span></li>
          <li><span class="howto-n">3</span><span>The closer you are, the higher your score. Three editions a day.</span></li>
        </ol>
        <div class="editors-note">
          <h2>Editor&rsquo;s Note</h2>
          <p>Every front page is a fingerprint of its moment. A country at war doesn&rsquo;t
          read like a country at peace. We give you four stories and want you to think:
          <em>when?</em> What is the feeling? Read and process to show your touch and
          understanding of history, and the lens we see it through. &mdash;
          <span class="signoff">The Editors</span></p>
        </div>
        <button id="play" class="primary">Play Today&rsquo;s Edition</button>
      </section>`;
    document.getElementById("play").addEventListener("click", startGame);
  }

  // ---- play screen ----
  function renderPlay() {
    const round = state.puzzle.rounds[state.round];
    setScoreboard();

    // The "picture" is the newspaper itself: a styled front page that works in
    // any era and never leaks the date (dateline is redacted). PRD §6.7.
    const [lead, ...rest] = round.stories;
    const story = (s, tag) => `
      <article class="${tag}">
        <h2>${escapeHtml(displayHeadline(s.headline))}</h2>
        ${s.summary ? `<p>${escapeHtml(s.summary)}</p>` : ""}
      </article>`;

    const newspaper = `
      <div class="newspaper">
        <div class="paper-masthead">
          <span class="paper-name">Times Search</span>
          <div class="paper-dateline">
            <span class="redacted">██████ ██, ████</span>
            <span class="redacted">No. ██,███</span>
          </div>
        </div>
        ${story(lead, "lead")}
        <div class="paper-columns">${rest.map((s) => story(s, "col")).join("")}</div>
      </div>`;

    const monthOpts = MONTHS.slice(1).map((m, i) =>
      `<option value="${i + 1}">${m}</option>`).join("");

    app.innerHTML = `
      <section class="screen play">
        <p class="prompt">Read the front page. When did it run?</p>
        ${newspaper}
        <form class="guess" id="guess-form" novalidate>
          <p class="guess-legend">When was this?</p>
          <div class="guess-fields">
            <label>Month
              <select id="month" required>
                <option value="" selected disabled>—</option>${monthOpts}
              </select>
            </label>
            <label>Year
              <input id="year" type="number" inputmode="numeric"
                     min="1851" max="2019" placeholder="1851–2019" required />
            </label>
          </div>
          <p class="error" id="guess-error" hidden></p>
          <button type="submit" class="primary">Go to Press</button>
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
          <span class="verdict-main">${Scoring.errorLabel(r.err)}</span>
          <span class="verdict-tone">${Scoring.toneMessage(r.err)}</span>
          <span class="verdict-points" id="vpoints">+0</span>
        </p>
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
  // NOTE: percentile/distribution is STUBBED locally pending the backend
  // score-distribution service (PRD §7.1).
  function syntheticDistribution() {
    // 10 buckets across 0..maxTotal, a plausible bell-ish shape.
    return [2, 5, 9, 14, 18, 19, 15, 10, 6, 2];
  }

  function percentileTop(total) {
    const dist = syntheticDistribution();
    const sum = dist.reduce((a, b) => a + b, 0);
    const bucket = Math.min(9, Math.floor(total / (Scoring.maxTotal / 10)));
    let below = 0;
    for (let i = 0; i < bucket; i++) below += dist[i];
    const pct = Math.round((below / sum) * 100);
    return { topPct: Math.max(1, 100 - pct), bucket, dist };
  }

  function renderResults() {
    scoreboard.hidden = true;
    const { topPct, bucket, dist } = percentileTop(state.total);
    const max = Math.max(...dist);

    const bars = dist.map((c, i) => `
      <div class="bar ${i === bucket ? "you" : ""}"
           style="height:${Math.round((c / max) * 100)}%"
           title="${i === bucket ? "You" : ""}"></div>`).join("");

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
        <p class="percentile">You were in the <strong>top ${topPct}%</strong> of players today
          <span class="stub-note">(demo estimate)</span></p>
        <div class="histogram">${bars}</div>
        <h3>Today&rsquo;s New York Times history&hellip;</h3>
        <ul class="recap">${recap}</ul>
        <div class="actions">
          <button id="home" class="secondary">Home</button>
          <button id="share" class="primary">Share</button>
        </div>
        <p class="toast" id="toast" hidden></p>
      </section>`;

    countUp(document.getElementById("ftotal"), state.total, "", 850);
    document.getElementById("home").addEventListener("click", renderHome);
    document.getElementById("share").addEventListener("click", share);
  }

  function shareText() {
    const squares = state.results.map((r) => Scoring.shareSquare(r.err)).join("");
    return `Times Search — ${state.puzzle.date}\n${squares}  ` +
      `${state.total.toLocaleString()}/${Scoring.maxTotal.toLocaleString()}`;
  }

  async function share() {
    const text = shareText();
    try {
      if (navigator.share) { await navigator.share({ text }); return; }
      await navigator.clipboard.writeText(text);
      toast("Copied to clipboard!");
    } catch (_) { toast("Couldn't share — here it is:\n" + text); }
  }

  function toast(msg) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = msg; t.hidden = false;
    setTimeout(() => { t.hidden = true; }, 2500);
  }

  function startGame() {
    state.round = 0; state.results = []; state.total = 0;
    renderPlay();
  }

  // ---- boot ----
  async function init() {
    app.innerHTML = `<section class="screen loading"><p>Setting the type&hellip;</p></section>`;
    try {
      const res = await fetch(PUZZLE_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      state.puzzle = await res.json();
      renderHome();
    } catch (e) {
      app.innerHTML = `<section class="screen error">
        <h2>Couldn&rsquo;t load today&rsquo;s edition</h2>
        <p>${escapeHtml(String(e))}</p>
        <p class="hint">Serve from the repo root: <code>python3 -m http.server</code>,
          then open <code>/web/</code>.</p></section>`;
    }
  }

  init();
})();
