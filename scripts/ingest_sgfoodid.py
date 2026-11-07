"""Ingest SG FoodID (HPB) exports into food_reference.

Step 1 (no --map):   python -m scripts.ingest_sgfoodid
    Prints every file's columns + sample rows, then STOPS so you can confirm the layout.
Step 2 (with --map): python -m scripts.ingest_sgfoodid --map scripts/sgfoodid_map.yaml [--dry-run]
    Applies the YAML column map, normalises, and upserts (idempotent on source+source_id).
See scripts/sgfoodid_map.example.yaml for the map format.
"""
import argparse
import csv
import re
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from scripts._common import ROOT, load_env

from api.services.foodref import NUTRIENTS, build_food_row, nutrient_dict, parse_number

RAW_DIR = ROOT / "data" / "raw" / "sgfoodid"
SUFFIXES = {".csv", ".xlsx", ".xlsm"}


def read_table(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    """Read a CSV or XLSX file into (headers, rows)."""
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames or []), list(reader)
    import openpyxl  # local-script dependency (requirements-scripts.txt)

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    it = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(it, [])]
    return headers, [dict(zip(headers, r)) for r in it if any(c is not None for c in r)]


def list_files(raw_dir: Path = RAW_DIR) -> list[Path]:
    return sorted(p for p in raw_dir.rglob("*") if p.suffix.lower() in SUFFIXES and not p.name.startswith("~$"))


def inspect(files: list[Path], samples: int = 3) -> None:
    for p in files:
        headers, rows = read_table(p)
        print(f"\n=== {p}  ({len(rows)} rows)")
        for i, h in enumerate(headers):
            print(f"  [{i}] {h!r}")
        for r in rows[:samples]:
            print("  sample:", {k: r[k] for k in headers if r.get(k) not in (None, "")})


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _split_aliases(v: Any) -> list[str]:
    return [a.strip() for a in re.split(r"[;|,]", str(v)) if a.strip()] if v else []


def map_row(row: dict[str, Any], m: dict, file_stem: str) -> dict | None:
    """Apply the YAML column map to one raw row -> food_reference row (or None if unusable)."""
    name = str(row.get(m["name"]) or "").strip()
    sid_col = m.get("source_id")
    source_id = str(row.get(sid_col)).strip() if sid_col and row.get(sid_col) not in (None, "") else _slug(name)
    scale = m.get("scale") or {}

    def nutrients(key: str) -> dict | None:
        cols = m.get(key) or {}
        return nutrient_dict({n: row.get(c) for n, c in cols.items()}, scale)

    aliases = [a for col in (m.get("aliases") or []) for a in _split_aliases(row.get(col))]
    return build_food_row(
        "sgfoodid", source_id, name, aliases=aliases,
        food_group=(str(row.get(m["food_group"])).strip() if m.get("food_group") and row.get(m["food_group"]) else None),
        serving_desc=(str(row.get(m["serving_desc"])).strip() if m.get("serving_desc") and row.get(m["serving_desc"]) else None),
        serving_g=parse_number(row.get(m["serving_g"])) if m.get("serving_g") else None,
        per_serving=nutrients("per_serving"), per_100g=nutrients("per_100g"),
    )


def validate_map(m: dict, headers: list[str], fname: str) -> list[str]:
    needed = [m.get("name"), m.get("serving_g"), m.get("food_group"), m.get("serving_desc"), m.get("source_id")]
    for key in ("per_serving", "per_100g"):
        needed += list((m.get(key) or {}).values())
    needed += m.get("aliases") or []
    errs = [f"{fname}: column {c!r} not found" for c in needed if c and c not in headers]
    for key in ("per_serving", "per_100g"):
        bad = set((m.get(key) or {})) - set(NUTRIENTS)
        errs += [f"map {key}: unknown nutrient {b!r} (use {NUTRIENTS})" for b in bad]
    if not m.get("name"):
        errs.append("map: 'name' is required")
    if not (m.get("per_serving") or m.get("per_100g")):
        errs.append("map: need per_serving and/or per_100g")
    return errs


def ingest(files: list[Path], m: dict, dry_run: bool) -> int:
    rows_out: dict[str, dict] = {}
    skipped = 0
    pattern = m.get("file_glob", "*")
    for p in files:
        if not fnmatch(p.name, pattern):
            continue
        headers, rows = read_table(p)
        errs = validate_map(m, headers, p.name)
        if errs:
            print("\n".join(errs))
            return 1
        n_ok = 0
        for r in rows:
            out = map_row(r, m, p.stem)
            if out is None:
                skipped += 1
            else:
                rows_out[out["source_id"]] = out  # later files/rows win on duplicate ids
                n_ok += 1
        print(f"{p.name}: {n_ok} usable / {len(rows)} rows")
    print(f"\nTotal unique foods: {len(rows_out)}  skipped (no name/kcal): {skipped}")
    if dry_run:
        for r in list(rows_out.values())[:3]:
            print("sample:", r)
        print("Dry run: nothing written.")
        return 0
    from api.db import Db

    db = Db()
    db.upsert_many("food_reference", list(rows_out.values()), "source,source_id")
    print(f"Upserted {len(rows_out)} rows. sgfoodid rows in DB now: {db.count('food_reference', source='eq.sgfoodid')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", type=Path, action="append", help="YAML column map (repeatable)")
    ap.add_argument("--dir", type=Path, default=RAW_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    files = list_files(args.dir)
    if not files:
        print(f"No CSV/XLSX files found in {args.dir}. See BUILD_PLAN.md Part 3.1.")
        return 1
    if not args.map:
        inspect(files)
        print("\nSTOP: confirm these columns, then create a YAML map (see scripts/sgfoodid_map.example.yaml)"
              " and re-run with --map.")
        return 0
    import yaml

    load_env()
    code = 0
    for mp in args.map:
        code |= ingest(files, yaml.safe_load(mp.read_text()), args.dry_run)
    return code


if __name__ == "__main__":
    sys.exit(main())
