import csv
import io
import json

import pytest

from backend.services.calc import CalcConfig
from backend.services.foodref import build_food_row
from backend.services.llm import LLMFatal, LLMTransient
from backend.services.resolver import Resolver
from scripts import eval as ev
from tests.fakes import FakeRepo


def write_labels(path, rows, header=("filename", "expected_dish", "expected_kcal")):
    with path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def make_image(path, size=(3000, 2000)):
    from PIL import Image
    Image.new("RGB", size, (200, 120, 40)).save(path, "JPEG")


def item_json(name, kcal=600, aliases=(), unit="plate"):
    return json.dumps({"items": [{"name": name, "aliases": list(aliases), "is_composite_dish": True,
                                  "portion": {"amount": 1, "unit": unit, "est_grams": 300},
                                  "est_nutrients": {"kcal": kcal}, "confidence": 0.8}]})


class Scripted:
    def __init__(self, *outs): self.outs, self.models = list(outs), []
    def complete(self, *, models, messages, timeout):
        self.models.append(models)
        o = self.outs.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def resolver():
    row = build_food_row("sgfoodid", "1", "Chicken rice", aliases=["Hainanese chicken rice"], serving_g=300,
                         per_serving={"kcal": 607.0})
    return Resolver(FakeRepo([row]))


def test_load_labels(tmp_path):
    p = tmp_path / "l.csv"
    write_labels(p, [["a.jpg", "Laksa", "589"], ["b.jpg", " Roti prata ", "209.5"]])
    assert ev.load_labels(p) == [ev.Label("a.jpg", "Laksa", 589.0), ev.Label("b.jpg", "Roti prata", 209.5)]
    write_labels(p, [["a.jpg", "x"]], header=("filename", "expected_dish"))
    with pytest.raises(ValueError, match="expected_kcal"):
        ev.load_labels(p)
    write_labels(p, [["a.jpg", "x", "lots"]])
    with pytest.raises(ValueError, match="line 2"):
        ev.load_labels(p)


def test_prep_image_resizes_and_strips(tmp_path):
    p = tmp_path / "a.jpg"; make_image(p)
    data, mime = ev.prep_image(p)
    from PIL import Image
    assert mime == "image/jpeg" and max(Image.open(io.BytesIO(data)).size) == 1280 and len(data) < 1_000_000
    raw, m2 = ev.prep_image(p, resize=False)
    assert raw == p.read_bytes() and m2 == "image/jpeg"
    png = tmp_path / "b.png"; png.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ev.prep_image(png, resize=False)[1] == "image/png"


def test_dish_match():
    assert ev.dish_match("Chicken rice", ["Hainanese chicken rice"])
    assert ev.dish_match("Char kway teow", ["char kuay teow"])
    assert not ev.dish_match("Laksa", ["Chicken rice", ""])
    assert not ev.dish_match("Laksa", [])


def case(provider, label=ev.Label("a.jpg", "Chicken rice", 600), res=None, cfg=CalcConfig()):
    return ev.evaluate_case("m1", label, b"\xff\xd8\xffx", "image/jpeg", provider, res, cfg)


def test_evaluate_case_with_resolver():
    p = Scripted(item_json("Chicken rice"))
    r = case(p, res=resolver())
    assert r.ok and r.recognised and r.resolved is True and r.kcal_pred == 607 and r.kcal_abs_error == 7
    assert p.models == [["m1"]] and r.items == ["Chicken rice"]  # single model, no fallback list


def test_evaluate_case_without_resolver_uses_model_estimate():
    r = case(Scripted(item_json("Chicken rice", kcal=550)))
    assert r.resolved is None and r.kcal_pred == 550 and r.kcal_abs_error == 50


def test_evaluate_case_miss_not_food_and_failures():
    assert case(Scripted(item_json("Laksa")), res=resolver()).recognised is False
    nf = case(Scripted('{"not_food": true}'), res=resolver())
    assert nf.ok and not nf.recognised and nf.kcal_pred is None and nf.kcal_abs_error is None
    for exc, text in [(LLMTransient("429"), "LLMTransient"), (LLMFatal("401"), "LLMFatal")]:
        r = case(Scripted(exc))
        assert not r.ok and text in r.error
    bad = case(Scripted("sorry, no"))
    assert not bad.ok and "ParseError" in bad.error


def test_summarize_and_report():
    rs = [
        ev.CaseResult("m1", "a", True, latency=1.0, recognised=True, resolved=True, kcal_pred=650, kcal_expected=600),
        ev.CaseResult("m1", "b", True, latency=3.0, recognised=False, resolved=False, kcal_pred=400, kcal_expected=600),
        ev.CaseResult("m1", "c", False, error="x"),
        ev.CaseResult("m2", "a", False, error="y"),
    ]
    s = ev.summarize(rs)
    assert s["m1"]["n"] == 3 and s["m1"]["failures"] == 1 and s["m1"]["failure_rate"] == pytest.approx(100 / 3)
    assert s["m1"]["recognition"] == 50 and s["m1"]["resolver"] == 50 and s["m1"]["mae_kcal"] == 125
    assert s["m1"]["latency_mean"] == 2.0 and s["m1"]["latency_p95"] == 3.0
    assert s["m2"]["recognition"] is None and s["m2"]["mae_kcal"] is None and s["m2"]["latency_mean"] is None
    report = ev.format_report(s)
    assert "| m1 | 3 | 33% | 50% | 50% | 125 | 2.0 / 3.0 |" in report
    assert "| m2 | 1 | 100% | n/a | n/a | n/a | n/a / n/a |" in report


def test_run_skips_missing_files_and_calls_each_model(tmp_path):
    make_image(tmp_path / "a.jpg", (200, 100))
    labels = [ev.Label("a.jpg", "Chicken rice", 600), ev.Label("missing.jpg", "Laksa", 500)]
    logs = []
    p = Scripted(*[item_json("Chicken rice")] * 2)
    out = ev.run(labels, tmp_path, ["m1", "m2"], p, None, log=logs.append, sleep=0)
    assert [r.model for r in out] == ["m1", "m2"] and p.models == [["m1"], ["m2"]]
    assert any("not found" in line for line in logs)


def test_main_dry_run_mock_and_guards(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VISION_MODELS", "m1,m2")
    for k in ("OPENROUTER_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(ev, "load_env", lambda: None)
    imgs = tmp_path / "images"; imgs.mkdir()
    write_labels(tmp_path / "l.csv", [[f"{i}.jpg", "Chicken rice", "600"] for i in range(30)])
    for i in range(30):
        make_image(imgs / f"{i}.jpg", (100, 80))
    base = ["--labels", str(tmp_path / "l.csv"), "--images", str(imgs), "--out", str(tmp_path / "out")]

    assert ev.main(base + ["--dry-run"]) == 0 and "30 images x 2 models = 60 model calls" in capsys.readouterr().out
    assert ev.main(base) == 1 and "OPENROUTER_API_KEY" in capsys.readouterr().out
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert ev.main(base) == 2 and "Refusing" in capsys.readouterr().out  # 60 calls > 45, no --yes

    assert ev.main(base + ["--mock", "--limit", "3", "--no-resolver"]) == 0
    out = capsys.readouterr().out
    assert "| m1 | 3 |" in out and "100%" in out  # the mock always returns chicken rice
    files = sorted(p.suffix for p in (tmp_path / "out").iterdir())
    assert files == [".csv", ".md"]
    rows = list(csv.DictReader(open(next((tmp_path / "out").glob("*.csv")))))
    assert len(rows) == 6 and rows[0]["model"] == "m1" and rows[0]["recognised"] == "True"


def test_main_input_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ev, "load_env", lambda: None)
    assert ev.main(["--labels", str(tmp_path / "nope.csv")]) == 1
    write_labels(tmp_path / "l.csv", [["a.jpg", "x", "1"]])
    monkeypatch.delenv("VISION_MODELS", raising=False)
    assert ev.main(["--labels", str(tmp_path / "l.csv")]) == 1 and "No models" in capsys.readouterr().out
    monkeypatch.setenv("VISION_MODELS", "m1")
    args = ["--labels", str(tmp_path / "l.csv"), "--images", str(tmp_path), "--mock", "--no-resolver", "--out", str(tmp_path / "o")]
    assert ev.main(args) == 1 and "No images were evaluated" in capsys.readouterr().out
