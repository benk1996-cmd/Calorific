import json

import httpx
import pytest

from backend.schemas import AnalysisResult, FoodItem
from backend.services.analyzer import MAX_ATTEMPTS, Analyzer, AnalysisError, QuotaExceeded, ServiceBusy
from backend.services.llm import LLMFatal, LLMTransient, MockProvider, OpenRouterProvider
from backend.services.parsing import ParseError, extract_json, parse_result

GOOD = json.dumps({"items": [{"name": "Laksa", "portion": {"amount": "1", "unit": "bowl", "est_grams": "600g"},
                               "est_nutrients": {"kcal": "589 kcal"}, "confidence": 1.7}]})
MODELS = ["a", "b", "c"]


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here you go: {"a": {"b": 2}} hope it helps') == {"a": {"b": 2}}
    assert extract_json('<think>{"x":0}</think>[1, 2]') == [1, 2]
    assert extract_json('bad { then {"ok": true}') == {"ok": True}
    with pytest.raises(ParseError):
        extract_json("no json here")


def test_parse_result_tolerance():
    r = parse_result(GOOD)
    i = r.items[0]
    assert i.portion.est_grams == 600 and i.est_nutrients.kcal == 589 and i.confidence == 1.0
    assert parse_result(json.dumps([{"name": "Egg"}])).items[0].name == "Egg"
    assert parse_result('{"not_food": true}').not_food
    assert parse_result('{"items": []}').not_food
    with pytest.raises(ParseError):
        parse_result('{"items": [{"name": ""}]}')
    f = FoodItem(name="x", aliases=None, components=[{"name": "rice"}, "egg"], modifiers="less rice",
                 portion={"amount": 0, "unit": ""}, est_nutrients={"kcal": "n/a"})
    assert f.components == ["rice", "egg"] and f.modifiers == ["less rice"] and f.aliases == []
    assert f.portion.amount == 1.0 and f.portion.unit == "serving" and f.est_nutrients.kcal == 0
    assert FoodItem(name="x", confidence="high").confidence == 0.5


class Seq:
    """Provider returning/raising a scripted sequence; records models used."""
    def __init__(self, *steps): self.steps, self.used = list(steps), []
    def complete(self, *, models, messages, timeout):
        self.used.append(models)
        s = self.steps.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def analyzer(provider, budget=99):
    left = {"n": budget}
    def consume():
        if left["n"] <= 0:
            return False
        left["n"] -= 1
        return True
    return Analyzer(provider, consume), left


def test_success_single_call():
    p = Seq(GOOD); a, left = analyzer(p)
    assert a.analyze_text("laksa", MODELS).items[0].name == "Laksa"
    assert left["n"] == 98 and p.used == [MODELS]


def test_transient_retries_with_single_models_and_counts_quota():
    p = Seq(LLMTransient("x"), LLMTransient("x"), GOOD); a, left = analyzer(p)
    a.analyze_text("laksa", MODELS)
    assert p.used == [MODELS, ["a"], ["b"]] and left["n"] == 96


def test_all_attempts_fail_is_busy():
    p = Seq(*[LLMTransient("x")] * MAX_ATTEMPTS); a, _ = analyzer(p)
    with pytest.raises(ServiceBusy):
        a.analyze_text("laksa", MODELS)


def test_bad_json_retries_once_then_errors():
    p = Seq("nope", GOOD); a, left = analyzer(p)
    assert a.analyze_text("x", MODELS).items and left["n"] == 97
    p = Seq("nope", "still nope"); a, _ = analyzer(p)
    with pytest.raises(AnalysisError):
        a.analyze_text("x", MODELS)


def test_quota_checked_before_every_call():
    p = Seq(GOOD); a, _ = analyzer(p, budget=0)
    with pytest.raises(QuotaExceeded):
        a.analyze_text("x", MODELS)
    assert p.used == []
    p = Seq("nope", GOOD); a, _ = analyzer(p, budget=1)  # retry would exceed the cap
    with pytest.raises(QuotaExceeded):
        a.analyze_text("x", MODELS)


def test_fatal_provider_error_shows_provider_message():
    a, _ = analyzer(Seq(LLMFatal("HTTP 401: No auth credentials found")))
    with pytest.raises(AnalysisError, match="No auth credentials found"):
        a.analyze_text("x", MODELS)


def test_four_models_are_split_into_groups_of_three():
    four = ["a", "b", "c", "d"]
    p = Seq(LLMTransient("x"), LLMTransient("x"), GOOD); a, _ = analyzer(p)
    a.analyze_text("laksa", four)
    assert p.used == [["a", "b", "c"], ["d"], ["a"]]
    assert all(len(u) <= 3 for u in p.used)


def test_photo_message_has_image_and_note():
    p = Seq(GOOD); a, _ = analyzer(p)
    seen = {}
    orig = p.complete
    p.complete = lambda **k: (seen.update(k), orig(**k))[1]
    a.analyze_photo(b"\xff\xd8\xffdata", "image/jpeg", "no sugar", MODELS)
    parts = seen["messages"][-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,") and "no sugar" in parts[0]["text"]


def or_client(handler):
    return OpenRouterProvider("KEY", "http://app", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_openrouter_request_shape_and_content():
    seen = {}
    def h(req):
        seen["body"], seen["h"] = json.loads(req.content), req.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": [{"text": "hi "}, {"text": "there"}]}}]})
    assert or_client(h).complete(models=["a", "b"], messages=[], timeout=5) == "hi there"
    assert seen["body"]["models"] == ["a", "b"] and "model" not in seen["body"]
    assert seen["body"]["reasoning"] == {"enabled": False}  # keeps reasoning models from using up the token budget
    assert seen["h"]["authorization"] == "Bearer KEY" and seen["h"]["x-title"] == "Calorific" and seen["h"]["http-referer"] == "http://app"
    or_client(h).complete(models=["solo"], messages=[], timeout=5)
    assert seen["body"]["model"] == "solo"


@pytest.mark.parametrize("resp,exc", [
    (httpx.Response(429), LLMTransient), (httpx.Response(402), LLMTransient), (httpx.Response(503), LLMTransient),
    (httpx.Response(401), LLMFatal), (httpx.Response(200, text="<html>"), LLMTransient),
    (httpx.Response(200, json={"error": {"message": "x"}}), LLMTransient),
    (httpx.Response(200, json={"choices": []}), LLMTransient),
    (httpx.Response(200, json={"choices": [{"message": {"content": "  "}}]}), LLMTransient),
])
def test_openrouter_errors(resp, exc):
    with pytest.raises(exc):
        or_client(lambda r: resp).complete(models=["a"], messages=[], timeout=5)


def test_openrouter_never_sends_more_than_three_models():
    seen = {}
    def h(req):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
    or_client(h).complete(models=["a", "b", "c", "d"], messages=[], timeout=5)
    assert seen["body"]["models"] == ["a", "b", "c"]


def test_openrouter_fatal_error_carries_provider_message():
    r = httpx.Response(400, json={"error": {"message": "'models' array must have 3 items or fewer.", "code": 400}})
    with pytest.raises(LLMFatal, match="HTTP 400: 'models' array must have 3 items or fewer"):
        or_client(lambda req: r).complete(models=["a"], messages=[], timeout=5)
    for body in (httpx.Response(401, text="<html>"), httpx.Response(403, json={"error": "plain string"}),
                 httpx.Response(404, json={"error": {}})):
        with pytest.raises(LLMFatal, match="HTTP 4"):
            or_client(lambda req, b=body: b).complete(models=["a"], messages=[], timeout=5)


def test_openrouter_network_error():
    def boom(req): raise httpx.ReadTimeout("slow")
    with pytest.raises(LLMTransient):
        or_client(boom).complete(models=["a"], messages=[], timeout=5)


def test_mock_provider_photo_and_text():
    m = MockProvider()
    photo = parse_result(m.complete(models=[], messages=[{"role": "user", "content": [{"type": "text"}]}], timeout=1))
    assert photo.items[0].name == "Chicken rice"
    t = parse_result(m.complete(models=[], messages=[{"role": "user", "content": "USER_TEXT: 2 roti prata + teh tarik, chicken rice less rice"}], timeout=1))
    names = [i.name for i in t.items]
    assert names == ["roti prata", "teh tarik", "chicken rice"]
    assert t.items[0].portion.amount == 2 and t.items[2].modifiers == ["less rice"]
    k = parse_result(m.complete(models=[], messages=[{"role": "user", "content": "USER_TEXT: kopi-o kosong"}], timeout=1))
    assert k.items[0].modifiers == ["kosong"]
    assert parse_result(m.complete(models=[], messages=[{"role": "user", "content": "USER_TEXT:  + "}], timeout=1)).not_food
