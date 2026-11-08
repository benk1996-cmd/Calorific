"""Runs one analysis (photo or text) through the LLM with quota accounting and fallbacks.

Every model request calls consume() first, so retries count against the daily quota.
Flow: request with up to 3 models (OpenRouter's limit per request); on a transient failure try the next
group of models, then single models in turn;
on unparseable output retry once with a "valid JSON only" nudge. At most MAX_ATTEMPTS requests."""
import base64
import logging
from typing import Callable

from backend.schemas import AnalysisResult
from backend.services.llm import MAX_MODELS_PER_REQUEST, LLMFatal, LLMProvider, LLMTransient
from backend.services.parsing import ParseError, parse_result

log = logging.getLogger("calorific")
MAX_ATTEMPTS = 3
SCHEMA = (
    '{"not_food": false, "items": [{"name": str, "aliases": [str], "cuisine": str, '
    '"is_composite_dish": bool, "components": [str], "modifiers": [str], '
    '"portion": {"amount": number, "unit": str, "est_grams": number}, '
    '"est_nutrients": {"kcal": number, "protein_g": number, "carbs_g": number, "fat_g": number, '
    '"sugar_g": number, "sodium_mg": number, "fibre_g": number}, "confidence": number 0-1}]}'
)
VISION_SYSTEM = (
    "You are a nutrition assistant for users in Singapore. Look at the meal photo and list EVERY food and "
    "drink. Prefer Singapore HPB-style dish names (e.g. 'Chicken rice', 'Char kway teow', 'Teh tarik'). "
    "Treat a standard hawker plate or bowl as ONE composite dish (is_composite_dish true, list components). "
    "Estimate grams using the plate, bowl or utensils for scale. For drinks, put the sugar level in the name "
    "(kopi O kosong / siew dai / regular). Put requests like 'less rice' in modifiers. Nutrients are for the whole "
    "portion shown. If the image is not food, return {\"not_food\": true, \"items\": []}. "
    "Reply with JSON only, no prose, matching: " + SCHEMA
)
TEXT_SYSTEM = (
    "You are a nutrition assistant for users in Singapore. Convert the user's free-text meal description into "
    "items. Handle quantities ('2 pieces'), modifiers ('less rice', 'no sugar', 'extra egg' go in modifiers) and "
    "Singlish drink codes (kopi-o kosong, teh-c siew dai: keep the full drink name incl. sugar level). Prefer "
    "HPB-style dish names; a standard hawker plate or bowl is ONE composite dish. portion.amount is the number "
    "of units. Nutrients are for the whole portion. If the text is not food, return {\"not_food\": true, "
    "\"items\": []}. Reply with JSON only, no prose, matching: " + SCHEMA
)


class QuotaExceeded(Exception):
    pass


class ServiceBusy(Exception):
    pass


class AnalysisError(Exception):
    pass


def photo_messages(image: bytes, mime: str, note: str | None = None) -> list[dict]:
    """Chat messages for a photo analysis (shared by the app and scripts/eval.py)."""
    url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    prompt = "Identify the food in this photo." + (f" User note: {note}" if note else "")
    return [
        {"role": "system", "content": VISION_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]},
    ]


class Analyzer:
    def __init__(self, provider: LLMProvider, consume: Callable[[], bool], *, timeout: float = 60):
        self.provider, self.consume, self.timeout = provider, consume, timeout

    def analyze_photo(self, image: bytes, mime: str, note: str | None, models: list[str]) -> AnalysisResult:
        return self._run(models, photo_messages(image, mime, note))

    def analyze_text(self, text: str, models: list[str]) -> AnalysisResult:
        messages = [{"role": "system", "content": TEXT_SYSTEM}, {"role": "user", "content": f"USER_TEXT: {text}"}]
        return self._run(models, messages)

    def _run(self, models: list[str], messages: list[dict]) -> AnalysisResult:
        if not models:
            raise AnalysisError("No AI models are configured")
        n = MAX_MODELS_PER_REQUEST
        groups = [models[i : i + n] for i in range(0, len(models), n)]
        use, group, idx, parse_retried, msgs = groups[0], 1, 0, False, list(messages)
        for _ in range(MAX_ATTEMPTS):
            if not self.consume():
                raise QuotaExceeded()
            try:
                text = self.provider.complete(models=use, messages=msgs, timeout=self.timeout)
            except LLMTransient:
                if group < len(groups):
                    use, group = groups[group], group + 1
                else:
                    use, idx = [models[idx % len(models)]], idx + 1
                continue
            except LLMFatal as e:
                log.error("AI provider rejected the request: %s", e)
                raise AnalysisError(f"The AI provider rejected the request ({e})") from None
            try:
                return parse_result(text)
            except ParseError:
                if parse_retried:
                    raise AnalysisError("Could not read the AI's answer. Please try again.") from None
                parse_retried = True
                msgs = msgs + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "Return valid JSON only, matching the schema. No prose, no code fences."},
                ]
        raise ServiceBusy()
