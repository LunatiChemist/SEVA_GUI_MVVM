from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, TYPE_CHECKING

from ..domain.ports import StoragePort, UseCaseError, WellId

if TYPE_CHECKING:  # pragma: no cover
    from ..viewmodels.experiment_vm import ExperimentVM


@dataclass
class SavePlateLayout:
    storage: StoragePort

    def __call__(
        self,
        name: str,
        wells: Optional[Iterable[WellId]] = None,
        params: Optional[Dict] = None,
        *,
        experiment_vm: Optional["ExperimentVM"] = None,
        selection: Optional[Iterable[WellId]] = None,
    ) -> Path:
        try:
            if experiment_vm is not None:
                payload = self._build_payload_from_vm(experiment_vm, selection)
            else:
                selection_list = list(wells or [])
                params_dict: Dict = params or {}
                well_params_map = self._normalize_params(selection_list, params_dict)
                payload = {
                    "selection": selection_list,
                    "well_params_map": well_params_map,
                }
            return self.storage.save_layout(name, payload)
        except Exception as e:
            raise UseCaseError("SAVE_LAYOUT_FAILED", str(e))

    def _build_payload_from_vm(
        self,
        experiment_vm: "ExperimentVM",
        selection: Optional[Iterable[WellId]],
    ) -> Dict[str, Any]:
        source_params: Dict[str, Dict[str, Any]] = getattr(
            experiment_vm, "well_params", {}
        )
        base_selection: Iterable[WellId] = (
            selection
            if selection is not None
            else getattr(experiment_vm, "selection", list(source_params.keys()))
        )
        selection_list = list(base_selection)
        well_params_map = self._normalize_params(selection_list, source_params)
        combined_selection = list(dict.fromkeys(selection_list + list(well_params_map.keys())))
        experiment_vm.well_params = {
            wid: dict(snapshot) for wid, snapshot in well_params_map.items()
        }
        experiment_vm.set_selection(set(combined_selection))  # type: ignore[arg-type]
        return {"selection": combined_selection, "well_params_map": well_params_map}

    def _normalize_params(
        self, selection: Iterable[str], params: Dict
    ) -> Dict[str, Dict[str, Any]]:
        if not isinstance(params, dict):
            raise ValueError("Layout parameters must be provided as dict.")
        is_per_well = params and all(isinstance(v, dict) for v in params.values())
        result: Dict[str, Dict[str, Any]] = {}
        if is_per_well:
            for wid, snapshot in params.items():
                sid = str(wid)
                result[sid] = dict(snapshot)
            for wid in selection:
                sid = str(wid)
                if sid not in result:
                    result[sid] = {}
        else:
            template = dict(params)
            for wid in selection:
                sid = str(wid)
                result[sid] = dict(template)
        return result
