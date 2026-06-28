"""Minimal Groq chat client (OpenAI-compatible), zero dependencies."""
import json
import urllib.request

from . import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(messages, temperature=0.2, max_tokens=200, json_mode=False):
    """Call Groq chat completions and return the message content string.
    Raises on transport/HTTP errors; callers decide how to fall back."""
    key = config.env("GROQ_API_KEY", required=True)
    payload = {
        "model": config.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        GROQ_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 # Cloudflare blocks the default Python-urllib UA (error 1010).
                 "User-Agent": "times-search/0.1"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"].strip()
