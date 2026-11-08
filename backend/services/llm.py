"""LLM provider interface, OpenRouter implementation (free models, `models` fallback array) and a mock."""
import json
import re
from typing import Protocol

import httpx

BASE_URL = "https://openrouter.ai/api/v1"
RETRYABLE = {408, 429, 500, 502, 503, 504, 402}
MAX_MODELS_PER_REQUEST = 3  # OpenRouter rejects a `models` array with more than 3 entries (HTTP 400)


class LLMTransient(Exception):
    """Rate limit / provider down / timeout: another model or attempt may succeed."""


class LLMFatal(Exception):
    """Misconfiguration (bad key, bad request): retrying will not help."""


class LLMProvider(Protocol):
    def complete(self, *, models: list[str], messages: list[dict], timeout: float) -> str: ...


def _error_message(r: httpx.Response) -> str:
    """OpenRouter's own error text (e.g. bad key, unknown model, data-policy). Never contains our key."""
    try:
        err = r.json().get("error", {})
        return str(err.get("message") if isinstance(err, dict) else err)[:160] or "no details"
    except (ValueError, AttributeError):
        return "no details"


class OpenRouterProvider:
    def __init__(self, api_key: str, app_url: str, *, http: httpx.Client | None = None):
        self.http = http or httpx.Client()
        self.headers = {
            "Authorization": f"Bearer {api_key}", "HTTP-Referer": app_url, "X-Title": "Calorific",
        }

    def complete(self, *, models: list[str], messages: list[dict], timeout: float) -> str:
        models = models[:MAX_MODELS_PER_REQUEST]
        # reasoning off: some free models (e.g. Nemotron) otherwise spend the whole token budget thinking and
        # return empty content. Models without a reasoning mode ignore the field.
        body: dict = {"messages": messages, "temperature": 0.2, "max_tokens": 1500, "reasoning": {"enabled": False}}
        if len(models) == 1:
            body["model"] = models[0]
        else:
            body["models"] = models  # OpenRouter falls through the list server-side
        try:
            r = self.http.post(f"{BASE_URL}/chat/completions", json=body, headers=self.headers, timeout=timeout)
        except httpx.HTTPError as e:
            raise LLMTransient(f"network: {type(e).__name__}") from None
        if r.status_code in RETRYABLE:
            raise LLMTransient(f"status {r.status_code}")
        if r.status_code != 200:
            raise LLMFatal(f"HTTP {r.status_code}: {_error_message(r)}")
        try:
            data = r.json()
        except ValueError:
            raise LLMTransient("non-JSON response") from None
        if data.get("error"):
            raise LLMTransient("provider error")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMTransient("empty response") from None
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not content or not str(content).strip():
            raise LLMTransient("empty content")
        return str(content)


_QTY = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:x|pcs?|pieces?|plates?|bowls?|cups?|glass(?:es)?)?\s+", re.I)
_MODS = ("less rice", "no sugar", "extra egg", "kosong", "siew dai")


class MockProvider:
    """Deterministic stand-in so development never spends the free quota."""

    def complete(self, *, models: list[str], messages: list[dict], timeout: float) -> str:
        last = messages[-1]["content"]
        if isinstance(last, list):  # photo request
            item = {
                "name": "Chicken rice", "aliases": ["Hainanese chicken rice"], "cuisine": "Singaporean",
                "is_composite_dish": True, "components": ["rice", "chicken"], "modifiers": [],
                "portion": {"amount": 1, "unit": "plate", "est_grams": 350},
                "est_nutrients": {"kcal": 600, "protein_g": 28, "carbs_g": 75, "fat_g": 20,
                                  "sugar_g": 3, "sodium_mg": 1100, "fibre_g": 2},
                "confidence": 0.8,
            }
            return json.dumps({"not_food": False, "items": [item]})
        text = last.split("USER_TEXT:", 1)[-1].strip()
        items = []
        for piece in re.split(r"\s*(?:\+|,|&|\band\b)\s*", text):
            if not piece.strip():
                continue
            m = _QTY.match(piece + " ")
            amount = float(m.group(1)) if m else 1.0
            name = _QTY.sub("", piece + " ").strip()
            mods = [x for x in _MODS if x in name.lower()]
            for x in ("less rice", "extra egg"):
                name = re.sub(x, "", name, flags=re.I).strip(" ,-")
            items.append({
                "name": name or piece.strip(), "modifiers": mods,
                "portion": {"amount": amount, "unit": "serving", "est_grams": 250 * amount},
                "est_nutrients": {"kcal": 300 * amount, "protein_g": 10, "carbs_g": 40, "fat_g": 10,
                                  "sugar_g": 5, "sodium_mg": 600, "fibre_g": 2},
                "confidence": 0.6,
            })
        return json.dumps({"not_food": not items, "items": items})
