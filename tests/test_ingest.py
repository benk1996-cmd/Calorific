import csv

import pytest
from fastapi.testclient import TestClient

from backend.auth import User, get_current_user
from backend.db import get_db
from backend.main import app
from scripts import ingest_sgfoodid as sg
from scripts import ingest_usda as us

MAP = {
    "name": "Food Name", "source_id": "ID", "aliases": ["Other"], "food_group": "Group",
    "serving_desc": "Serving", "serving_g": "Serving g",
    "per_serving": {"kcal": "kcal", "protein_g": "Protein", "sodium_mg": "Sodium g"},
    "scale": {"sodium_mg": 1000},
}


def write_csv(path, header, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def test_sg_inspect_and_map(tmp_path, capsys):
    p = tmp_path / "a.csv"
    write_csv(p, ["ID", "Food Name", "Other", "Group", "Serving", "Serving g", "kcal", "Protein", "Sodium g"],
              [["1", "Laksa", "Curry laksa; Laksa lemak", "Noodles", "1 bowl", "600", "589", "20", "2.1"],
               ["2", "", "", "", "", "", "", "", ""], ["3", "NoKcal", "", "", "", "", "-", "", ""]])
    assert sg.main(["--dir", str(tmp_path)]) == 0
    assert "STOP" in capsys.readouterr().out
    h, rows = sg.read_table(p)
    assert sg.validate_map(MAP, h, "a.csv") == []
    out = sg.map_row(rows[0], MAP, "a")
    assert out["aliases"] == ["Curry laksa", "Laksa lemak"] and out["per_serving"]["sodium_mg"] == 2100
    assert out["per_100g"]["kcal"] == pytest.approx(98.1666, rel=1e-3)
    assert sg.map_row(rows[1], MAP, "a") is None and sg.map_row(rows[2], MAP, "a") is None


def test_sg_validate_map_errors_and_dry_run(tmp_path, capsys):
    errs = sg.validate_map({"name": "Nope", "per_serving": {"bogus": "kcal"}}, ["kcal"], "f")
    assert any("Nope" in e for e in errs) and any("bogus" in e for e in errs)
    assert "need per_serving" in " ".join(sg.validate_map({"name": "kcal"}, ["kcal"], "f"))
    p = tmp_path / "a.csv"
    write_csv(p, ["Food Name", "kcal"], [["Laksa", "589"], ["Laksa", "600"]])
    m = {"name": "Food Name", "per_100g": {"kcal": "kcal"}}
    assert sg.ingest([p], m, dry_run=True) == 0
    assert "Total unique foods: 1" in capsys.readouterr().out  # duplicate slug ids collapse (idempotent)
    assert sg.ingest([p], {"name": "Missing", "per_100g": {"kcal": "kcal"}}, True) == 1
    assert sg.main(["--dir", str(tmp_path / "empty")]) == 1


def test_sg_xlsx(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Food Name", "kcal"]); ws.append(["Roti prata", 209]); ws.append([None, None])
    p = tmp_path / "b.xlsx"; wb.save(p)
    h, rows = sg.read_table(p)
    assert h == ["Food Name", "kcal"] and len(rows) == 1
    assert sg.list_files(tmp_path) == [p]


def test_usda_load_folder_and_dry_run(tmp_path, capsys):
    d = tmp_path / "foundation"; d.mkdir()
    write_csv(d / "food.csv", ["fdc_id", "data_type", "description"],
              [["1", "foundation_food", "Egg, raw"], ["2", "branded_food", "Junk"], ["3", "foundation_food", "No kcal"]])
    write_csv(d / "food_nutrient.csv", ["id", "fdc_id", "nutrient_id", "amount"],
              [["1", "1", "1008", "143"], ["2", "1", "1003", "12.6"], ["3", "1", "9999", "5"],
               ["4", "2", "1008", "1"], ["5", "3", "1003", "2"]])
    rows = us.load_folder(d, "foundation_food")
    assert len(rows) == 1 and rows[0]["name"] == "Egg, raw" and rows[0]["per_100g"]["protein_g"] == 12.6
    assert us.main(["--dir", str(tmp_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "foundation: 1 foods" in out and "sr_legacy: skipped" in out
    assert us.main(["--dir", str(tmp_path / "none"), "--dry-run"]) == 0


class SearchDb:
    def __init__(self): self.calls = []
    def rpc(self, fn, args):
        self.calls.append((fn, args))
        return [{"id": 1, "source": "sgfoodid", "source_id": "x", "name": "Laksa", "score": 0.9, "is_exact": True,
                 "serving_g": 600, "per_serving": {"kcal": 589}, "per_100g": {"kcal": 98}}]


def test_search_endpoint():
    db = SearchDb()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: User("A", "a@x.com")
    try:
        c = TestClient(app)
        r = c.get("/api/foods/search", params={"q": "laksa"})
        assert r.status_code == 200 and r.json()["results"][0]["name"] == "Laksa"
        assert db.calls[0][0] == "search_foods" and db.calls[0][1]["p_source"] is None
        assert c.get("/api/foods/search", params={"q": "a"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_search_requires_auth():
    assert TestClient(app).get("/api/foods/search", params={"q": "laksa"}).status_code == 401
