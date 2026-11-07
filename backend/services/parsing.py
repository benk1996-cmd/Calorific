"""Tolerant extraction of the model's JSON (code fences, <think> blocks, surrounding prose)."""
import json
import re

from pydantic import ValidationError

from backend.schemas import AnalysisResult


class ParseError(Exception):
    pass


def extract_json(text: str) -> dict | list:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t)
    dec = json.JSONDecoder()
    for m in re.finditer(r"[{\[]", t):
        try:
            obj, _ = dec.raw_decode(t[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, (dict, list)):
            return obj
    raise ParseError("no JSON found")


def parse_result(text: str) -> AnalysisResult:
    obj = extract_json(text)
    if isinstance(obj, list):
        obj = {"items": obj}
    try:
        res = AnalysisResult.model_validate(obj)
    except ValidationError as e:
        raise ParseError(str(e)) from None
    if not res.items:
        res = AnalysisResult(not_food=True, items=[])
    return res
