import csv
import json

from seva.adapters.storage_local import StorageLocal


def test_save_layout_persists_flags(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))
    wells = ["A1"]
    snapshot = {
        "cv.vertex1_v": "0.5",
        "run_cv": "1",
        "run_ac": "0",
        "run_dc": "0",
        "run_eis": "0",
        "eval_cdl": "1",
    }

    storage.save_layout("layout_flags", wells, {"A1": snapshot})
    loaded = storage.load_layout("layout_flags")

    snap = loaded["well_params_map"]["A1"]
    assert snap["run_cv"] == "1"
    assert snap["run_ac"] == "0"
    assert snap["eval_cdl"] == "1"
    assert snap["cv.vertex1_v"] == "0.5"

    layout_path = tmp_path / "layout_flags.csv"
    with layout_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    payload = json.loads(rows[0]["params_json"])
    assert "fields" in payload
    assert "flags" in payload
    assert payload["flags"]["run_cv"] == "1"
    assert payload["fields"]["cv.vertex1_v"] == "0.5"


def test_load_layout_defaults_missing_flags(tmp_path):
    layout_path = tmp_path / "legacy_layout.csv"
    with layout_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["well_id", "params_json"])
        writer.writerow(["A1", json.dumps({"cv.vertex1_v": "0.25"})])

    storage = StorageLocal(root_dir=str(tmp_path))
    loaded = storage.load_layout("legacy_layout")

    snap = loaded["well_params_map"]["A1"]
    assert snap["cv.vertex1_v"] == "0.25"
    assert snap["run_cv"] == "0"
    assert snap["run_dc"] == "0"
    assert snap["run_ac"] == "0"
    assert snap["run_eis"] == "0"
    assert snap["eval_cdl"] == "0"
