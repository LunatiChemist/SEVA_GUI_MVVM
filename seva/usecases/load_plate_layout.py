from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from ..domain.layout_utils import normalize_selection
from ..domain.ports import StoragePort, UseCaseError

if TYPE_CHECKING:  # pragma: no cover
    from ..viewmodels.experiment_vm import ExperimentVM
    from ..viewmodels.plate_vm import PlateVM


@dataclass
class LoadPlateLayout:
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
            selection = normalize_selection(data.get("selection"))
            well_params_map = data.get("well_params_map") or {}
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
        store = getattr(experiment_vm, "well_params", None)
        if isinstance(store, dict):
            store.clear()
            for wid, snapshot in well_params_map.items():
                store[str(wid)] = dict(snapshot)
        elif hasattr(experiment_vm, "save_params_for"):
            for wid, snapshot in well_params_map.items():
                experiment_vm.save_params_for(str(wid), snapshot)  # type: ignore[arg-type]

        if hasattr(experiment_vm, "set_selection"):
            try:
                experiment_vm.set_selection(set(selection))  # type: ignore[arg-type]
            except Exception:
                setattr(experiment_vm, "selection", set(selection))
        else:
            setattr(experiment_vm, "selection", set(selection))

        if selection:
            first = selection[0]
            current = well_params_map.get(first)
            if current and hasattr(experiment_vm, "fields"):
                setattr(experiment_vm, "fields", dict(current))

    def _apply_to_plate_vm(
        self,
        plate_vm: "PlateVM",
        selection: List[str],
        well_params_map: Dict[str, Dict],
    ) -> None:
        configured_wells = list(well_params_map.keys())
        if hasattr(plate_vm, "clear_all_configured"):
            plate_vm.clear_all_configured()
        if configured_wells and hasattr(plate_vm, "mark_configured"):
            plate_vm.mark_configured(configured_wells)
        if hasattr(plate_vm, "set_selection"):
            plate_vm.set_selection(selection)
        else:
            setattr(plate_vm, "_selected", set(selection))
