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
        """Load a saved layout and optionally apply it to live viewmodels.

        Args:
            name: Layout name or path known to ``StoragePort``.
            experiment_vm: Optional experiment VM target for in-memory updates.
            plate_vm: Optional plate VM target for configured/selected wells.

        Returns:
            Dict: Payload containing ``selection`` and ``well_params_map``.

        Side Effects:
            Reads persisted JSON-like payload and mutates provided VMs.

        Call Chain:
            Toolbar load action -> ``LoadPlateLayout.__call__`` ->
            ``StoragePort.load_layout`` -> optional VM apply helpers.

        Usage:
            Restore prior plate setup without embedding storage logic in views.

        Raises:
            UseCaseError: If storage access or payload normalization fails.
        """
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
        """Apply loaded selection and params to the experiment viewmodel.

        Args:
            experiment_vm: VM that owns active field values and well params.
            selection: Well ids selected in the stored layout.
            well_params_map: Per-well parameter snapshots from storage.

        Returns:
            None.

        Side Effects:
            Replaces ``experiment_vm.well_params``, updates selection, and
            hydrates current field values from the first selected well.
        """
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
        """Apply loaded configured/selected wells to the plate viewmodel.

        Args:
            plate_vm: VM that tracks configured and selected wells in the UI.
            selection: Wells that should be selected after load.
            well_params_map: Per-well parameters used to derive configured wells.

        Returns:
            None.

        Side Effects:
            Resets configured flags, marks configured wells, and sets selection.
        """
        configured_wells = list(well_params_map.keys())
        plate_vm.clear_all_configured()
        if configured_wells:
            plate_vm.mark_configured(configured_wells)
        plate_vm.set_selection(selection)
