"""Evaluate each vision model on your own labelled photos (REAL model calls, unless --mock).

    python -m scripts.eval --dry-run                    # show how many calls it would make
    python -m scripts.eval --limit 10 --models google/gemma-4-31b-it:free
    python -m scripts.eval --mock --no-resolver         # pipeline smoke test, no key, no quota

Inputs: eval/images/<file> and eval/labels.csv with columns filename,expected_dish,expected_kcal.
Reports per model: recognition accuracy, resolver accuracy, mean absolute kcal error, latency, failure rate.

QUOTA: the free OpenRouter tier allows 50 calls/day for the whole account. Calls = images x models,
so the script refuses more than 45 planned calls unless you pass --yes. Each call is one request
(no retries or fallbacks) so the numbers reflect the raw model.
"""
import argparse
import csv
import io
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from scripts._common import ROOT, load_env

from backend.services.analyzer import photo_messages
from backend.services.calc import CalcConfig, compute_item, config_from_env
from backend.services.llm import LLMFatal, LLMProvider, LLMTransient, MockProvider, OpenRouterProvider
from backend.services.parsing import ParseError, parse_result
from backend.services.pipeline import build_item_rows
from backend.services.resolver import Resolver
from backend.services.textsim import similarity

MATCH_THRESHOLD = 0.5
FREE_DAILY_SAFE_CALLS = 45
MAX_DIM, JPEG_QUALITY = 1280, 85


@dataclass(frozen=True)
class Label:
    filename: str
    expected_dish: str
    expected_kcal: float


@dataclass
class CaseResult:
    model: str
    filename: str
    ok: bool
    error: str = ""
    latency: float = 0.0
    recognised: bool = False
    resolved: bool | None = None  # None = resolver unavailable
    kcal_pred: float | None = None
    kcal_expected: float = 0.0
    items: list[str] = field(default_factory=list)

    @property
    def kcal_abs_error(self) -> float | None:
        return None if self.kcal_pred is None else abs(self.kcal_pred - self.kcal_expected)


def load_labels(path: Path) -> list[Label]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = {"filename", "expected_dish", "expected_kcal"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
        out = []
        for n, r in enumerate(reader, start=2):
            try:
                out.append(Label(r["filename"].strip(), r["expected_dish"].strip(), float(r["expected_kcal"])))
            except (TypeError, ValueError):
                raise ValueError(f"{path.name} line {n}: expected_kcal must be a number") from None
    return out


def prep_image(path: Path, resize: bool = True) -> tuple[bytes, str]:
    """Load an image like the app would send it: <=1280px JPEG, metadata stripped."""
    data = path.read_bytes()
    if not resize:
        return data, "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((MAX_DIM, MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY)  # re-encoding drops EXIF/GPS
    return buf.getvalue(), "image/jpeg"


def dish_match(expected: str, candidates: list[str]) -> bool:
    e = expected.lower().strip()
    return any(c and (similarity(e, c) >= MATCH_THRESHOLD or e in c.lower() or c.lower() in e) for c in candidates)


def evaluate_case(
    model: str, label: Label, image: bytes, mime: str, provider: LLMProvider, resolver: Resolver | None,
    cfg: CalcConfig = CalcConfig(), timeout: float = 60,
) -> CaseResult:
    res = CaseResult(model=model, filename=label.filename, ok=False, kcal_expected=label.expected_kcal)
    t0 = time.monotonic()
    try:
        text = provider.complete(models=[model], messages=photo_messages(image, mime), timeout=timeout)
        result = parse_result(text)
    except (LLMTransient, LLMFatal, ParseError) as e:
        res.latency, res.error = time.monotonic() - t0, f"{type(e).__name__}: {e}"[:120]
        return res
    res.latency, res.ok = time.monotonic() - t0, True
    res.items = [i.name for i in result.items]
    names = [n for i in result.items for n in (i.name, *i.aliases)]
    res.recognised = dish_match(label.expected_dish, names)
    if result.not_food or not result.items:
        return res
    if resolver is None:
        res.kcal_pred = sum(compute_item(i, None, cfg).nutrients["kcal"] for i in result.items)
        return res
    res.resolved = any(
        r.food is not None and dish_match(label.expected_dish, [r.food.name])
        for r in (resolver.resolve(i.name, i.aliases) for i in result.items)
    )
    res.kcal_pred = sum(row["kcal"] for row in build_item_rows(result, resolver, cfg))
    return res


def _pct(xs: list[bool]) -> float | None:
    return 100.0 * sum(xs) / len(xs) if xs else None


def summarize(results: list[CaseResult]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for model in dict.fromkeys(r.model for r in results):
        rs = [r for r in results if r.model == model]
        ok = [r for r in rs if r.ok]
        lat = sorted(r.latency for r in ok)
        errs = [r.kcal_abs_error for r in ok if r.kcal_abs_error is not None]
        res = [r.resolved for r in ok if r.resolved is not None]
        out[model] = {
            "n": len(rs), "failures": len(rs) - len(ok), "failure_rate": 100.0 * (len(rs) - len(ok)) / len(rs),
            "recognition": _pct([r.recognised for r in ok]), "resolver": _pct(res),
            "mae_kcal": statistics.mean(errs) if errs else None,
            "latency_mean": statistics.mean(lat) if lat else None,
            "latency_p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None,
        }
    return out


def _f(v: float | None, fmt: str) -> str:
    return "n/a" if v is None else format(v, fmt)


def format_report(summary: dict[str, dict]) -> str:
    rows = ["| Model | Cases | Failure rate | Recognition | Resolver | MAE kcal | Latency mean / p95 (s) |",
            "|---|---|---|---|---|---|---|"]
    for m, s in summary.items():
        rows.append(f"| {m} | {s['n']} | {s['failure_rate']:.0f}% | {_f(s['recognition'], '.0f')}% | "
                    f"{_f(s['resolver'], '.0f')}% | {_f(s['mae_kcal'], '.0f')} | "
                    f"{_f(s['latency_mean'], '.1f')} / {_f(s['latency_p95'], '.1f')} |")
    return "\n".join(rows).replace("n/a%", "n/a")


def run(
    labels: list[Label], images: Path, models: list[str], provider: LLMProvider, resolver: Resolver | None, *,
    resize: bool = True, sleep: float = 0.0, log: Callable[[str], None] = print,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    cfg = config_from_env()
    for label in labels:
        path = images / label.filename
        if not path.exists():
            log(f"skip {label.filename}: file not found")
            continue
        image, mime = prep_image(path, resize)
        for model in models:
            r = evaluate_case(model, label, image, mime, provider, resolver, cfg)
            results.append(r)
            log(f"{model:45s} {label.filename:14s} {'ok ' if r.ok else 'ERR'} {r.latency:5.1f}s "
                f"{'recognised' if r.recognised else r.error or 'missed'}")
            if sleep:
                time.sleep(sleep)  # free tier: 20 requests/minute
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images", type=Path, default=ROOT / "eval" / "images")
    ap.add_argument("--labels", type=Path, default=ROOT / "eval" / "labels.csv")
    ap.add_argument("--models", help="comma-separated; default VISION_MODELS from .env")
    ap.add_argument("--limit", type=int, help="only the first N labelled images")
    ap.add_argument("--sleep", type=float, default=3.5, help="seconds between calls (default 3.5 = under 20/min)")
    ap.add_argument("--yes", action="store_true", help=f"allow more than {FREE_DAILY_SAFE_CALLS} planned calls")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    ap.add_argument("--mock", action="store_true", help="use the mock provider (no key, no quota)")
    ap.add_argument("--no-resolver", action="store_true", help="skip the database lookup (model estimates only)")
    ap.add_argument("--no-resize", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    args = ap.parse_args(argv)
    load_env()

    try:
        labels = load_labels(args.labels)
    except (OSError, ValueError) as e:
        print(f"Cannot read labels: {e}")
        return 1
    if args.limit:
        labels = labels[: args.limit]
    models = [m.strip() for m in (args.models or os.getenv("VISION_MODELS", "")).split(",") if m.strip()]
    if not models:
        print("No models: set VISION_MODELS in .env or pass --models")
        return 1
    calls = len(labels) * len(models)
    print(f"{len(labels)} images x {len(models)} models = {calls} model calls")
    if args.dry_run:
        return 0
    if not args.mock:
        if not os.getenv("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY is not set (use --mock for a smoke test)")
            return 1
        if calls > FREE_DAILY_SAFE_CALLS and not args.yes:
            print(f"Refusing: {calls} calls would exceed the free tier's 50/day. Use --limit or --models to cut it "
                  f"down, or --yes if you know your quota allows it.")
            return 2

    resolver = None
    if not args.no_resolver and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        from backend.config import get_settings
        from backend.db import Db
        from backend.services.foodrepo import DbFoodRepo
        from backend.services.usda import UsdaClient

        s, repo = get_settings(), DbFoodRepo(Db())
        resolver = Resolver(repo, UsdaClient(s.usda_api_key, repo) if s.usda_api_key else None, threshold=s.resolver_threshold)
    elif not args.no_resolver:
        print("Supabase not configured: resolver accuracy will be n/a and kcal uses the model's own estimates.")

    provider: LLMProvider = MockProvider() if args.mock else OpenRouterProvider(
        os.environ["OPENROUTER_API_KEY"], os.getenv("APP_URL", "http://localhost:5173"))
    results = run(labels, args.images, models, provider, resolver, resize=not args.no_resize,
                  sleep=0 if args.mock else args.sleep)
    if not results:
        print("No images were evaluated (check eval/images/ and filenames in labels.csv).")
        return 1
    report = format_report(summarize(results))
    print("\n" + report)
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    (args.out / f"eval_{stamp}.md").write_text(report + "\n")
    with (args.out / f"eval_{stamp}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "filename", "ok", "error", "latency_s", "recognised", "resolved", "kcal_pred",
                    "kcal_expected", "items"])
        for r in results:
            w.writerow([r.model, r.filename, r.ok, r.error, round(r.latency, 2), r.recognised, r.resolved,
                        "" if r.kcal_pred is None else round(r.kcal_pred), r.kcal_expected, "; ".join(r.items)])
    print(f"\nSaved to {args.out}/eval_{stamp}.(md|csv). Use it to order VISION_MODELS (best first).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
