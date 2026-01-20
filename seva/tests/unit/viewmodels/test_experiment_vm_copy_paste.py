from __future__ import annotations

from seva.tests.unit.viewmodels.helpers import make_experiment_vm_with_fields


def test_copy_paste_uses_form_snapshot_and_normalizes_flags() -> None:
    vm = make_experiment_vm_with_fields({
        "cv.start_v": "0.05",
        "cv.vertex1_v": "0.45",
        "cv.vertex2_v": "-0.35",
        "cv.final_v": "0.1",
        "cv.scan_rate_v_s": "0.25",
        "cv.cycles": "4",
        "run_cv": "1",
        "run_dc": "0",
        "run_ac": "0",
        "run_eis": "0",
        "run_lsv": "0",
        "run_cdl": "0",
        "eval_cdl": "0",
    })

    vm.save_params_for(
        "A1",
        {
            "cv.start_v": "0.0",
            "cv.vertex1_v": "legacy",
            "cv.vertex2_v": "-1.0",
            "cv.final_v": "0.0",
            "cv.scan_rate_v_s": "1.0",
            "cv.cycles": "1",
            "run_cv": "0",
            "run_dc": "1",
        },
    )

    vm.cmd_copy_mode("CV", "A1")

    assert vm.clipboard_cv["cv.vertex1_v"] == "0.45"
    assert vm.clipboard_cv["cv.cycles"] == "4"
    assert vm.clipboard_cv["run_cv"] == "1"

    vm.save_params_for(
        "B2",
        {
            "cv.vertex1_v": "0.0",
            "cv.vertex2_v": "0.0",
            "run_cv": "0",
            "run_dc": "1",
            "ea.duration_s": "90",
        },
    )

    vm.cmd_paste_mode("CV", ["B2", "C3"])

    expected_flags = {
        "run_cv": "1",
        "run_dc": "0",
        "run_ac": "0",
        "run_eis": "0",
        "run_lsv": "0",
        "run_cdl": "0",
        "eval_cdl": "0",
    }

    for wid in ("B2", "C3"):
        snapshot = vm.well_params[wid]
        for field in (
            "cv.start_v",
            "cv.vertex1_v",
            "cv.vertex2_v",
            "cv.final_v",
            "cv.scan_rate_v_s",
            "cv.cycles",
        ):
            assert snapshot[field] == vm.fields[field]
        for flag, value in expected_flags.items():
            assert snapshot[flag] == value

    assert vm.well_params["B2"]["ea.duration_s"] == "90"
