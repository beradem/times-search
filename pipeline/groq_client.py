"""Minimal Groq chat client (OpenAI-compatible), zero dependencies."""
import json
import time
import urllib.error
import urllib.request

from . import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(messages, temperature=0.2, max_tokens=200, json_mode=False, retries=4):
    """Call Groq chat completions and return the message content string.

    Retries transient failures and Groq's flaky JSON-mode rejections
    (json_validate_failed), nudging temperature up so a stuck deterministic
    output can change. Raises on the final failure; callers decide how to fall
    back."""
    key = config.env("GROQ_API_KEY", required=True)
    last = None
    for attempt in range(retries):
        payload = {
            "model": config.GROQ_MODEL,
            "messages": messages,
            "temperature": round(temperature + 0.15 * attempt, 2),
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            GROQ_URL, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     # Cloudflare blocks the default Python-urllib UA (error 1010).
                     "User-Agent": "paper-guessr/0.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            last = e
            # 400 = JSON-mode rejection (retry with a temp nudge); 429/5xx = transient.
            if e.code in (400, 429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise
    raise last
