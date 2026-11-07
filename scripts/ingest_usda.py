"""Ingest USDA FoodData Central bulk CSVs into food_reference (per-100g, 7 tracked nutrients only).

    python -m scripts.ingest_usda [--dry-run]

Reads data/raw/usda/{foundation,sr_legacy,fndds}/ (missing folders are skipped). Each folder needs
food.csv and food_nutrient.csv. Streams food_nutrient.csv so even FNDDS stays low-memory.
"""
import argparse
import csv
import sys
from pathlib import Path

from scripts._common import ROOT, load_env

from api.services.foodref import USDA_ENERGY_IDS, USDA_NUTRIENT_IDS, build_food_row, usda_nutrients

USDA_DIR = ROOT / "data" / "raw" / "usda"
FOLDERS = {"foundation": "foundation_food", "sr_legacy": "sr_legacy_food", "fndds": "survey_fndds_food"}
WANTED_IDS = {str(i) for i in (*USDA_ENERGY_IDS, *USDA_NUTRIENT_IDS)}


def load_folder(folder: Path, data_type: str) -> list[dict]:
    """Return normalised food_reference rows for one USDA folder."""
    foods: dict[str, tuple[str, str | None]] = {}
    with (folder / "food.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("data_type") == data_type and r.get("description"):
                foods[r["fdc_id"]] = (r["description"], r.get("food_category_id") or None)
    pairs: dict[str, list[tuple[int, str]]] = {}
    with (folder / "food_nutrient.csv").open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["nutrient_id"] in WANTED_IDS and r["fdc_id"] in foods:
                pairs.setdefault(r["fdc_id"], []).append((int(r["nutrient_id"]), r["amount"]))
    rows = []
    for fdc_id, (desc, _) in foods.items():
        row = build_food_row("usda", fdc_id, desc, per_100g=usda_nutrients(pairs.get(fdc_id, [])))
        if row:
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=USDA_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    load_env()
    db = None
    if not args.dry_run:
        from api.db import Db

        db = Db()
    total = 0
    for sub, dtype in FOLDERS.items():
        folder = args.dir / sub
        if not (folder / "food.csv").exists():
            print(f"{sub}: skipped (not found)")
            continue
        rows = load_folder(folder, dtype)
        print(f"{sub}: {len(rows)} foods with kcal")
        total += len(rows)
        if db:
            db.upsert_many("food_reference", rows, "source,source_id")
    if db and total:
        print(f"usda rows in DB: {db.count('food_reference', source='eq.usda')}")
        print(f"database size: {db.rpc('db_size_mb', {})} MB (free limit 500 MB)")
    elif not total:
        print("Nothing loaded. Check data/raw/usda/ layout (BUILD_PLAN.md Part 3.2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
