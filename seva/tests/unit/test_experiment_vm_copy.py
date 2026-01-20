from __future__ import annotations

from seva.tests.unit.viewmodels.helpers import make_experiment_vm_with_fields


def test_build_mode_snapshot_for_copy_filters_fields_and_sets_flags() -> None:
    vm = make_experiment_vm_with_fields({
        "cv.amplitude": "0.5",
        "cv.scan_rate": "25",
        "run_dc": "0",
        "run_eis": "0",
        "misc.note": "ignore",
    })

    snapshot = vm.build_mode_snapshot_for_copy("CV")

    assert snapshot == {
        "cv.amplitude": "0.5",
        "cv.scan_rate": "25",
        "run_cv": "1",
    }


def test_cmd_copy_mode_uses_source_snapshot() -> None:
    vm = make_experiment_vm_with_fields({})
    provided = {"cv.amplitude": "1.0", "run_cv": "1"}

    vm.cmd_copy_mode("CV", "A1", source_snapshot=provided)

    assert vm.clipboard_cv == provided
