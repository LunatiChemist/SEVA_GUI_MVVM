import json

from seva.adapters.storage_local import StorageLocal


def test_save_layout_roundtrip_preserves_flags(tmp_path):
    storage = StorageLocal(root_dir=str(tmp_path))
    payload = {
        "selection": ["A1"],
        "well_params_map": {
            "A1": {
                "cv.vertex1_v": "0.5",
                "run_cv": "1",
                "run_ac": "0",
                "run_dc": "0",
                "run_eis": "0",
                "eval_cdl": "1",
            }
        },
    }

    saved_path = storage.save_layout("layout_flags", payload)
    assert saved_path.name == "layout_flags.json"
    raw = json.loads(saved_path.read_text(encoding="utf-8"))
    assert raw["selection"] == ["A1"]
    flags = raw["well_params_map"]["A1"]["flags"]
    fields = raw["well_params_map"]["A1"]["fields"]
    assert flags["run_cv"] == "1"
    assert fields["cv.vertex1_v"] == "0.5"

    loaded = storage.load_layout("layout_flags")
    snap = loaded["well_params_map"]["A1"]
    assert snap["run_cv"] == "1"
    assert snap["run_ac"] == "0"
    assert snap["eval_cdl"] == "1"
    assert snap["cv.vertex1_v"] == "0.5"


def test_load_layout_defaults_missing_flags(tmp_path):
    payload = {
        "selection": ["A1"],
        "well_params_map": {
            "A1": {
                "fields": {"cv.vertex1_v": "0.25"},
            }
        },
    }
    layout_path = tmp_path / "layout_legacy.json"
    layout_path.write_text(json.dumps(payload), encoding="utf-8")

    storage = StorageLocal(root_dir=str(tmp_path))
    loaded = storage.load_layout("layout_legacy")

    snap = loaded["well_params_map"]["A1"]
    assert snap["cv.vertex1_v"] == "0.25"
    assert snap["run_cv"] == "0"
    assert snap["run_dc"] == "0"
    assert snap["run_ac"] == "0"
    assert snap["run_eis"] == "0"
    assert snap["eval_cdl"] == "0"
