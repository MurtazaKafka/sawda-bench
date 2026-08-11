"""Fireworks client with disk cache and cost tracking.

Every call is cached in calls/<model-short>.jsonl keyed by a sha256 of the
full request body, so reruns are free. Usage (tokens) is logged per call and
a running dollar estimate is available via cost_report().
"""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

from config import CALLS_DIR, PRICES

API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"


def _load_env():
    if os.environ.get("FIREWORKS_API_KEY"):
        return
    for envfile in (Path(__file__).resolve().parent.parent / ".env",):
        if envfile.exists():
            for line in envfile.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def _cache_path(model: str) -> Path:
    return CALLS_DIR / (model.rsplit("/", 1)[-1] + ".jsonl")


def _cache_key(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False)
                          .encode()).hexdigest()


def _load_cache(model: str) -> dict:
    cache = {}
    p = _cache_path(model)
    if p.exists():
        with p.open() as f:
            for line in f:
                rec = json.loads(line)
                cache[rec["key"]] = rec
    return cache


def call(model: str, messages: list, max_tokens: int = 1024,
         temperature: float = 0.0) -> dict:
    """Returns {'text', 'usage', 'cached'}. Deterministic (temp 0), cached."""
    _load_env()
    body = {"model": model, "messages": messages,
            "max_tokens": max_tokens, "temperature": temperature}
    key = _cache_key(body)
    cache = _load_cache(model)
    if key in cache:
        rec = cache[key]
        return {"text": rec["text"], "usage": rec["usage"], "cached": True}

    headers = {"Authorization": f"Bearer {os.environ['FIREWORKS_API_KEY']}",
               "Content-Type": "application/json"}
    for attempt in range(4):
        resp = requests.post(API_URL, headers=headers, json=body, timeout=180)
        if resp.status_code == 200:
            break
        if resp.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(2 ** attempt * 2)
            continue
        raise RuntimeError(f"Fireworks {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data["usage"]
    rec = {"key": key, "request": body, "text": text, "usage": usage,
           "ts": time.time()}
    with _cache_path(model).open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"text": text, "usage": usage, "cached": False}


def cost_report() -> str:
    """Dollar estimate per model from everything in calls/ (unique calls)."""
    lines, total = [], 0.0
    for p in sorted(CALLS_DIR.glob("*.jsonl")):
        n = tok_in = tok_out = 0
        model = None
        with p.open() as f:
            for line in f:
                rec = json.loads(line)
                model = rec["request"]["model"]
                n += 1
                tok_in += rec["usage"].get("prompt_tokens", 0)
                tok_out += rec["usage"].get("completion_tokens", 0)
        if not model:
            continue
        pi, po = PRICES.get(model, (0.0, 0.0))
        cost = tok_in / 1e6 * pi + tok_out / 1e6 * po
        total += cost
        lines.append(f"  {p.stem:<24} calls={n:<5} in={tok_in:<8} "
                     f"out={tok_out:<8} ${cost:.4f}")
    lines.append(f"  {'TOTAL':<24} {'':<32} ${total:.4f}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("API spend so far (unique cached calls):")
    print(cost_report())
