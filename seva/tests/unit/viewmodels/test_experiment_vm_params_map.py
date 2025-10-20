from __future__ import annotations

from seva.viewmodels.experiment_vm import ExperimentVM


def _cv_snapshot(**overrides: str) -> dict[str, str]:
    base = {
        "cv.start_v": "0.05",
        "cv.vertex1_v": "0.6",
        "cv.vertex2_v": "-0.4",
        "cv.final_v": "0.1",
        "cv.scan_rate_v_s": "0.5",
        "cv.cycles": "3",
        "run_cv": "1",
        "run_dc": "1",  # should be normalized to "0"
        "storage.client_datetime": "2024-10-10T12:00:00",
    }
    base.update(overrides)
    return base


def test_build_well_params_map_returns_cv_fields_and_flags_only() -> None:
    vm = ExperimentVM()
    vm.save_params_for("A1", _cv_snapshot())
    vm.save_params_for(
        "B2",
        _cv_snapshot(
            **{
                "cv.vertex1_v": "0.7",
                "cv.cycles": "7",
                "misc.note": "should be ignored",
            }
        ),
    )
    vm.save_params_for("C3", {"run_cv": "0"})  # inactive well should be skipped

    result = vm.build_well_params_map(["A1", "B2", "C3"])

    assert set(result.keys()) == {"A1", "B2"}

    flag_keys = {"run_cv", "run_dc", "run_ac", "run_eis", "run_lsv", "run_cdl", "eval_cdl"}
    cv_keys = {
        "cv.start_v",
        "cv.vertex1_v",
        "cv.vertex2_v",
        "cv.final_v",
        "cv.scan_rate_v_s",
        "cv.cycles",
    }
    allowed_keys = flag_keys | cv_keys

    a1_snapshot = result["A1"]
    assert set(a1_snapshot.keys()).issubset(allowed_keys)
    assert a1_snapshot["cv.vertex1_v"] == "0.6"
    assert a1_snapshot["run_cv"] == "1"
    for flag in flag_keys - {"run_cv"}:
        assert a1_snapshot[flag] == "0"
    assert "storage.client_datetime" not in a1_snapshot

    b2_snapshot = result["B2"]
    assert set(b2_snapshot.keys()).issubset(allowed_keys)
    assert b2_snapshot["cv.cycles"] == "7"
    assert b2_snapshot["run_cv"] == "1"
    for flag in flag_keys - {"run_cv"}:
        assert b2_snapshot[flag] == "0"
    assert "misc.note" not in b2_snapshot
