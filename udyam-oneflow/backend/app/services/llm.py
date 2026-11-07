"""Thin, provider-agnostic LLM adapter (language only - AGENTS.md invariant 1).

Providers are tried in config.LLM_PROVIDER order: Gemini first, then the
OpenRouter free models. Every call returns None on any failure (no key, rate
limit, timeout, bad JSON) so the caller falls back to the scripted advisor or
local OCR. Nothing here ever decides a price, product or eligibility result.
"""
from __future__ import annotations

import base64
import json
import re
import time

import httpx

from app import config

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

STATS = {"calls": 0, "ok": 0, "failed": 0, "by_provider": {}, "last_error": None,
         "validator_violations": 0}
_cooldown: dict[str, float] = {}   # provider/model -> time when it may be retried
COOLDOWN_S = 60


def providers() -> list[str]:
    names = [p.strip().lower() for p in config.LLM_PROVIDER.split(",") if p.strip()]
    out = []
    for name in names:
        if name == "gemini" and config.GEMINI_API_KEY:
            out.append(name)
        elif name == "openrouter" and config.OPENROUTER_API_KEY:
            out.append(name)
    return out


def enabled() -> bool:
    return bool(providers())


def status() -> dict:
    return {"enabled": enabled(), "providers": providers(), "gemini_model": config.GEMINI_MODEL,
            "openrouter_models": config.OPENROUTER_MODELS, **STATS}


def parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _cooling(key: str) -> bool:
    return _cooldown.get(key, 0) > time.time()


def _record(provider: str, ok: bool, error: str | None = None) -> None:
    STATS["calls"] += 1
    STATS["ok" if ok else "failed"] += 1
    per = STATS["by_provider"].setdefault(provider, {"ok": 0, "failed": 0})
    per["ok" if ok else "failed"] += 1
    if error:
        STATS["last_error"] = f"{provider}: {error[:160]}"


def _gemini(system: str, user: str, image: bytes | None, as_json: bool, max_tokens: int) -> str | None:
    key = f"gemini:{config.GEMINI_MODEL}"
    if _cooling(key):
        return None
    parts: list[dict] = [{"text": user}]
    if image is not None:
        parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(image).decode()}})
    body: dict = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        # Short language tasks: no hidden thinking (it eats the output budget and adds seconds).
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2,
                             "thinkingConfig": {"thinkingBudget": 0}},
    }
    if as_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    try:
        r = httpx.post(GEMINI_URL.format(model=config.GEMINI_MODEL), json=body,
                       headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=config.LLM_TIMEOUT_S)
        if r.status_code == 429:
            _cooldown[key] = time.time() + COOLDOWN_S
        if r.status_code != 200:
            _record("gemini", False, f"HTTP {r.status_code}")
            return None
        candidate = (r.json().get("candidates") or [{}])[0]
        if candidate.get("finishReason") not in (None, "STOP"):
            _record("gemini", False, f"finish {candidate.get('finishReason')}")
            return None   # truncated or blocked: never show half a sentence
        text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []))
        _record("gemini", bool(text))
        return text or None
    except httpx.HTTPError as exc:
        _record("gemini", False, type(exc).__name__)
        return None


def _openrouter(system: str, user: str, image: bytes | None, as_json: bool, max_tokens: int) -> str | None:
    content: list[dict] | str = user
    if image is not None:
        content = [{"type": "text", "text": user},
                   {"type": "image_url",
                    "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}}]
    for model in config.OPENROUTER_MODELS:
        key = f"openrouter:{model}"
        if _cooling(key):
            continue
        body: dict = {"model": model, "max_tokens": max_tokens, "temperature": 0.2,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        if as_json:
            body["response_format"] = {"type": "json_object"}
        try:
            r = httpx.post(OPENROUTER_URL, json=body, timeout=config.LLM_TIMEOUT_S,
                           headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"})
        except httpx.HTTPError as exc:
            _record("openrouter", False, type(exc).__name__)
            continue
        if r.status_code == 429:
            _cooldown[key] = time.time() + COOLDOWN_S
        choices = r.json().get("choices") if r.status_code == 200 else None
        complete_ = bool(choices) and choices[0].get("finish_reason") in (None, "stop")
        text = (choices[0].get("message", {}).get("content") or "") if complete_ else ""
        if text:
            _record("openrouter", True)
            return text
        _record("openrouter", False, f"{model} HTTP {r.status_code}")
    return None


def complete(system: str, user: str, *, image: bytes | None = None, as_json: bool = False,
             max_tokens: int = 1024) -> str | None:
    """First provider that answers wins. None means: use the deterministic fallback."""
    for provider in providers():
        fn = _gemini if provider == "gemini" else _openrouter
        text = fn(system, user, image, as_json, max_tokens)
        if text:
            return text
    return None


def warmup() -> None:
    """Open the provider connection at startup so the owner's first message isn't the slow one."""
    if enabled():
        complete("Reply with the single word OK.", "ping", max_tokens=5)


def complete_json(system: str, user: str, *, image: bytes | None = None, max_tokens: int = 1024) -> dict | None:
    return parse_json(complete(system, user, image=image, as_json=True, max_tokens=max_tokens))
