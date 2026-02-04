"""Use case for loading persisted plate-layout snapshots.

It reads storage payloads and can apply normalized selection/parameter state to
experiment and plate view models.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from ..domain.ports import StoragePort, UseCaseError

if TYPE_CHECKING:  # pragma: no cover
    from ..viewmodels.experiment_vm import ExperimentVM
    from ..viewmodels.plate_vm import PlateVM


@dataclass
class LoadPlateLayout:
    """Use-case callable for loading and optionally applying saved layouts.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    storage: StoragePort

    def __call__(
        self,
        name: str | Path,
        *,
        experiment_vm: Optional["ExperimentVM"] = None,
        plate_vm: Optional["PlateVM"] = None,
    ) -> Dict:
        try:
            data = self.storage.load_layout(name)
            selection = list(data.get("selection") or [])
            well_params_map = dict(data.get("well_params_map") or {})
            if experiment_vm is not None:
                self._apply_to_experiment_vm(experiment_vm, selection, well_params_map)
            if plate_vm is not None:
                self._apply_to_plate_vm(plate_vm, selection, well_params_map)
            return {"selection": selection, "well_params_map": well_params_map}
        except Exception as e:
            raise UseCaseError("LOAD_LAYOUT_FAILED", str(e))

    def _apply_to_experiment_vm(
        self,
        experiment_vm: "ExperimentVM",
        selection: List[str],
        well_params_map: Dict[str, Dict],
    ) -> None:
        experiment_vm.well_params.clear()
        for wid, snapshot in well_params_map.items():
            experiment_vm.well_params[str(wid)] = dict(snapshot)

        experiment_vm.set_selection(set(selection))  # type: ignore[arg-type]

        if selection:
            first = selection[0]
            current = well_params_map.get(first)
            if current:
                experiment_vm.fields = dict(current)

    def _apply_to_plate_vm(
        self,
        plate_vm: "PlateVM",
        selection: List[str],
        well_params_map: Dict[str, Dict],
    ) -> None:
        configured_wells = list(well_params_map.keys())
        plate_vm.clear_all_configured()
        if configured_wells:
            plate_vm.mark_configured(configured_wells)
        plate_vm.set_selection(selection)
