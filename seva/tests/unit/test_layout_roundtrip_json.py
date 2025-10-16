import json
from typing import Dict, Iterable, List

import pytest

from seva.adapters.storage_local import StorageLocal
from seva.usecases.save_plate_layout import SavePlateLayout
from seva.usecases.load_plate_layout import LoadPlateLayout
from seva.viewmodels.experiment_vm import ExperimentVM
from seva.viewmodels.plate_vm import PlateVM


SCENARIOS = [
    (
        "layout_cv_only",
        ["A1"],
        {
            "A1": {
                "run_cv": "1",
                "run_dc": "0",
                "run_ac": "0",
                "run_eis": "0",
                "run_lsv": "0",
                "run_cdl": "0",
                "eval_cdl": "0",
                "cv.start_v": "0.05",
                "cv.vertex1_v": "0.5",
                "cv.vertex2_v": "-0.5",
                "cv.final_v": "0.0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "3",
            },
        },
    ),
    (
        "layout_cv_cdl_mixed",
        ["A1", "B2"],
        {
            "A1": {
                "run_cv": "1",
                "run_dc": "0",
                "run_ac": "0",
                "run_eis": "0",
                "run_lsv": "0",
                "run_cdl": "0",
                "eval_cdl": "0",
                "cv.start_v": "0.05",
                "cv.vertex1_v": "0.45",
                "cv.vertex2_v": "-0.45",
                "cv.final_v": "0.02",
                "cv.scan_rate_v_s": "0.2",
                "cv.cycles": "2",
            },
            "B2": {
                "run_cv": "0",
                "run_dc": "0",
                "run_ac": "0",
                "run_eis": "0",
                "run_lsv": "0",
                "run_cdl": "1",
                "eval_cdl": "1",
                "cdl.vertex_a_v": "0.2",
                "cdl.vertex_b_v": "-0.2",
            },
        },
    ),
    (
        "layout_empty",
        [],
        {},
    ),
]


@pytest.mark.parametrize("layout_name, selection, snapshots", SCENARIOS)
def test_layout_round_trip_from_vm(tmp_path, layout_name, selection, snapshots):
    storage = StorageLocal(root_dir=str(tmp_path))
    save_usecase = SavePlateLayout(storage)
    load_usecase = LoadPlateLayout(storage)

    exp_vm = ExperimentVM()
    plate_vm = PlateVM()
    _prime_vm_state(exp_vm, plate_vm, selection, snapshots)

    layout_path = save_usecase(layout_name, experiment_vm=exp_vm)
    original_state = _capture_state(exp_vm, plate_vm)

    restored_exp_vm = ExperimentVM()
    restored_plate_vm = PlateVM()
    loaded = load_usecase(
        layout_name,
        experiment_vm=restored_exp_vm,
        plate_vm=restored_plate_vm,
    )
    restored_state = _capture_state(restored_exp_vm, restored_plate_vm)

    assert restored_state == original_state
    assert sorted(loaded["selection"]) == original_state["selection"]
    assert loaded["well_params_map"] == original_state["well_params"]

    if snapshots:
        with layout_path.open("r", encoding="utf-8") as fh:
            persisted = json.load(fh)
        for wid, snap in original_state["well_params"].items():
            persisted_entry = persisted["well_params_map"][wid]
            flags = persisted_entry.get("flags", {})
            fields = persisted_entry.get("fields", {})
            for key, value in snap.items():
                bucket = flags if key.startswith("run_") or key == "eval_cdl" else fields
                assert key in bucket
                assert bucket[key] == value


def _prime_vm_state(
    exp_vm: ExperimentVM,
    plate_vm: PlateVM,
    selection: Iterable[str],
    snapshots: Dict[str, Dict[str, str]],
) -> None:
    exp_vm.set_selection(set(selection))
    plate_vm.set_selection(selection)
    if snapshots:
        plate_vm.mark_configured(snapshots.keys())
    for wid, snap in snapshots.items():
        exp_vm.save_params_for(wid, snap)


def _capture_state(
    exp_vm: ExperimentVM, plate_vm: PlateVM
) -> Dict[str, Dict[str, str] | List[str]]:
    selection = sorted(str(w) for w in getattr(exp_vm, "selection", set()))
    well_params_raw = getattr(exp_vm, "well_params", {})
    well_params = {
        str(wid): dict(snapshot)
        for wid, snapshot in sorted(well_params_raw.items())
    }
    plate_selection = sorted(plate_vm.get_selection())
    configured = sorted(plate_vm.configured())
    return {
        "selection": selection,
        "well_params": well_params,
        "plate_selection": plate_selection,
        "configured": configured,
    }
