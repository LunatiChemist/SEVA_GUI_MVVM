from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from seva.adapters.storage_local import StorageLocal
from seva.usecases.load_plate_layout import LoadPlateLayout
from seva.usecases.save_plate_layout import SavePlateLayout
from seva.viewmodels.experiment_vm import ExperimentVM
from seva.viewmodels.plate_vm import PlateVM


def _base_params(**fields: str) -> Dict[str, str]:
    defaults: Dict[str, str] = {
        "run_cv": "0",
        "run_dc": "0",
        "run_ac": "0",
        "run_eis": "0",
        "run_lsv": "0",
        "run_cdl": "0",
        "eval_cdl": "0",
    }
    for key, value in fields.items():
        defaults[key] = str(value)
    return defaults


@pytest.mark.parametrize("selection_order", [["A1", "B2"], ["B2", "A1"]])
def test_layout_roundtrip_preserves_vm_and_plate_state(tmp_path: Path, selection_order) -> None:
    storage = StorageLocal(root_dir=str(tmp_path))
    saver = SavePlateLayout(storage)
    loader = LoadPlateLayout(storage)

    original_experiment = ExperimentVM()
    original_plate = PlateVM()

    params_a1 = _base_params(
        **{
            "run_cv": "1",
            "cv.vertex1_v": "0.10",
            "cv.vertex2_v": "0.40",
        }
    )
    params_b2 = _base_params(
        **{
            "run_dc": "1",
            "run_ac": "1",
            "ea.duration_s": "60",
            "ea.charge_cutoff_c": "2.5",
        }
    )

    original_experiment.save_params_for("A1", params_a1)
    original_experiment.save_params_for("B2", params_b2)
    original_experiment.set_selection(set(selection_order))
    original_plate.mark_configured(selection_order)
    original_plate.set_selection(selection_order)

    saved_path = saver(
        "layout_ui_roundtrip.json",
        experiment_vm=original_experiment,
        selection=selection_order,
    )

    restored_experiment = ExperimentVM()
    restored_plate = PlateVM()

    loader(saved_path, experiment_vm=restored_experiment, plate_vm=restored_plate)

    assert saved_path.exists()
    assert restored_plate.configured() == {"A1", "B2"}
    assert restored_plate.get_selection() == set(selection_order)
    assert restored_experiment.get_params_for("A1") == params_a1
    assert restored_experiment.get_params_for("B2") == params_b2
