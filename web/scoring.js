// Times Search — scoring (portable core; no DOM, reusable by a native client).
// Months-off with decaying points. See PRD section 5.
(function (global) {
  "use strict";

  const MAX_POINTS = 1000;
  const HALF_LIFE = 18; // months; the main "feel" dial (PRD §5.2)
  const ROUNDS = 3;

  function monthIndex(year, month) {
    return year * 12 + (month - 1);
  }

  // Absolute distance in months between a guess and the actual date.
  function errorMonths(guess, actual) {
    return Math.abs(monthIndex(guess.year, guess.month) -
                    monthIndex(actual.year, actual.month));
  }

  function roundPoints(err) {
    return Math.round(MAX_POINTS * Math.pow(0.5, err / HALF_LIFE));
  }

  // Tone copy shown on the reveal screen (PRD §5.3). Voiced, magnitude-based.
  function toneMessage(err) {
    if (err === 0) return "Bullseye — stop the presses.";
    if (err <= 3) return "Practically the same edition.";
    if (err <= 12) return "Right era, wrong season.";
    if (err <= 36) return "A few years adrift.";
    if (err <= 120) return "Wrong decade, friend.";
    return "Off by a generation.";
  }

  // "X months off" -> human string ("Exact!", "3 months off", "2 years off").
  function errorLabel(err) {
    if (err === 0) return "Exact!";
    if (err < 12) return err + (err === 1 ? " month off" : " months off");
    const years = Math.round(err / 12);
    return years + (years === 1 ? " year off" : " years off");
  }

  // Escalating "how far off" icon for the reveal screen — a dinosaur when
  // you're off by a lot. err is in months.
  function eraIcon(err) {
    if (err <= 6) return "🎯";
    if (err <= 24) return "🗓️";
    if (err <= 120) return "🕰️";
    if (err <= 360) return "🏛️";
    return "🦕";
  }

  // Spoiler-free share square per round (never reveals the date).
  function shareSquare(err) {
    if (err === 0) return "🟩";
    if (err <= 6) return "🟢";
    if (err <= 24) return "🟡";
    if (err <= 60) return "🟠";
    return "⬛";
  }

  const Scoring = {
    MAX_POINTS, HALF_LIFE, ROUNDS,
    monthIndex, errorMonths, roundPoints, toneMessage, errorLabel, eraIcon, shareSquare,
    maxTotal: MAX_POINTS * ROUNDS,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = Scoring;
  else global.Scoring = Scoring;
})(typeof window !== "undefined" ? window : globalThis);
