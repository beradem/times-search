# Times Search — backend setup

The game runs fully static on Vercel. Two optional pieces add live stats and
notifications. The **code is already in the repo**; these are the one-time
provisioning steps (they need your Vercel account, so they're on you).

Until these are configured, the game still works — the results screen just
falls back to a local score estimate and no notifications are sent.

---

## 1. Score distribution + daily play count + notifications

The endpoint is `api/score.js`. It needs a Redis store and (optionally) an
ntfy topic.

### a) Provision Upstash Redis (free tier)
1. Vercel dashboard → your **times-search** project → **Storage** →
   **Create Database** → **Upstash Redis** (Marketplace) → connect it to the
   project.
2. This automatically adds the env vars **`UPSTASH_REDIS_REST_URL`** and
   **`UPSTASH_REDIS_REST_TOKEN`** to the project. Nothing to copy by hand.

### b) Set up ntfy push notifications (free, no account)
1. Pick a **private, hard-to-guess topic name** — ntfy topics are public to
   anyone who knows the name, so treat it like a password, e.g.
   `times-search-bera-7Kq93fX`.
2. Vercel → project → **Settings → Environment Variables** → add
   **`NTFY_TOPIC`** = that topic string.
3. On your phone, install the **ntfy** app (iOS/Android) → **Subscribe to
   topic** → enter the exact same topic name.
4. You'll now get a push **every time someone completes a game**, including the
   running daily count.
   - *Volume note:* this is one push per completion. If the game gets popular
     it becomes a firehose — mute the topic in the app, or ask me to switch it
     to a once-a-day digest.

### c) Redeploy
Any push to `main` redeploys. After adding the env vars, trigger a redeploy
(Vercel → Deployments → ⋯ → Redeploy) so the function picks them up.

**Verify:** open the latest deployment → **Functions** tab → you should see
`api/score`. Finishing a game should then show "top X% of N players today" and
send you a push.

---

## 2. Visitor analytics (how many people show up)

The analytics script is already in `index.html`. Just enable it:

1. Vercel → project → **Analytics** tab → **Enable Web Analytics**.
2. Done — the dashboard shows daily visitors, top pages, referrers.

This tracks *visitors* (who lands on the site). Your `/api/score` count tracks
*completions* (who finishes). Between the two you can see the drop-off.

---

## Environment variables summary

| Variable | Set by | Purpose |
|---|---|---|
| `UPSTASH_REDIS_REST_URL` | Upstash integration (auto) | Redis REST endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash integration (auto) | Redis auth |
| `NTFY_TOPIC` | you | ntfy push topic for completion alerts |
| `NYT_API_KEY` | you (already set) | daily puzzle generation |
| `GROQ_API_KEY` | you (already set) | blurbs + summaries |

`NYT_API_KEY` / `GROQ_API_KEY` live in **GitHub** secrets (for the daily
Action). `UPSTASH_*` / `NTFY_TOPIC` live in **Vercel** env vars (for the
serverless function).
