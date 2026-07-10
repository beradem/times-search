// Records a completed game, returns the player's real daily placement, and
// pushes an ntfy notification. Talks to Upstash Redis over its REST API — no
// npm dependencies. Degrades gracefully (returns nulls) when unconfigured, so
// the client always has a working fallback.

const BUCKETS = 10;   // histogram bars
const MAX = 3000;     // max score: 3 rounds x 1000
const TTL = "5184000"; // keep daily keys 60 days

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const body = typeof req.body === "string" ? safeParse(req.body) : (req.body || {});
  const date = String(body.date || "");
  const score = Number(body.score);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
      !Number.isFinite(score) || score < 0 || score > MAX) {
    return res.status(400).json({ error: "bad input" });
  }
  const bucket = Math.min(BUCKETS - 1, Math.floor(score / (MAX / BUCKETS)));

  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) {
    return res.status(200).json({ count: null, topPct: null, dist: null });
  }

  let count = null;
  const dist = new Array(BUCKETS).fill(0);
  try {
    const r = await fetch(`${url}/pipeline`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify([
        ["INCR", `count:${date}`],
        ["EXPIRE", `count:${date}`, TTL],
        ["HINCRBY", `dist:${date}`, String(bucket), "1"],
        ["EXPIRE", `dist:${date}`, TTL],
        ["HGETALL", `dist:${date}`],
      ]),
    });
    const out = await r.json();
    count = out?.[0]?.result ?? null;
    const flat = out?.[4]?.result || [];
    for (let i = 0; i < flat.length; i += 2) {
      const b = Number(flat[i]);
      if (b >= 0 && b < BUCKETS) dist[b] = Number(flat[i + 1]);
    }
  } catch (_) {
    return res.status(200).json({ count: null, topPct: null, dist: null });
  }

  const total = dist.reduce((a, b) => a + b, 0) || 1;
  let below = 0;
  for (let b = 0; b < bucket; b++) below += dist[b];
  const topPct = Math.max(1, Math.min(100, Math.round(100 - (below / total) * 100)));

  await notify(score, count); // await so the request isn't torn down first
  return res.status(200).json({ count, topPct, dist });
}

function safeParse(s) { try { return JSON.parse(s); } catch { return {}; } }

async function notify(score, count) {
  const topic = process.env.NTFY_TOPIC;
  if (!topic) return;
  try {
    await fetch(`https://ntfy.sh/${encodeURIComponent(topic)}`, {
      method: "POST",
      headers: { Title: "Times Search", Tags: "newspaper" },
      body: `Someone finished today's puzzle — ${score.toLocaleString()}/${MAX}. ` +
            `That makes ${count} completed so far today.`,
    });
  } catch (_) { /* notification is best-effort */ }
}
