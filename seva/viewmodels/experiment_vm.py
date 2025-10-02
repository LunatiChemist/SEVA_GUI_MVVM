from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set, Iterable

WellId = str


@dataclass
class ExperimentVM:
    """Form state, validation, global Electrode Mode.

    - Holds transient parameter field values (strings from view)
    - Provides cross-field validation (lightweight here; domain in UseCases)
    - Emits commands to start/cancel via UseCases (wired by bootstrap)
    - Electrode mode is global: "2E" or "3E"; persists via StoragePort

    Future: LiveData could be added here.
    """

    # Signals to outside / UseCases
    on_start_requested: Optional[Callable[[Dict], None]] = (
        None  # Dict = ExperimentPlan DTO
    )
    on_cancel_group: Optional[Callable[[], None]] = None

    # UI state
    electrode_mode: str = "3E"  # "2E" | "3E"
    editing_well: Optional[WellId] = None
    selection: Set[WellId] = field(default_factory=set)

    # per-well persisted parameters (last applied values)
    well_params: Dict[WellId, Dict[str, str]] = field(default_factory=dict)

    # field store (flat string map from ExperimentPanelView)
    fields: Dict[str, str] = field(default_factory=dict)

    def set_field(self, field_id: str, value: str) -> None:
        self.fields[field_id] = value

    def set_selection(self, wells: Set[WellId]) -> None:
        self.selection = set(wells)

    def set_electrode_mode(self, mode: str) -> None:
        if mode not in ("2E", "3E"):
            raise ValueError("Invalid ElectrodeMode")
        self.electrode_mode = mode

    def build_experiment_plan(self) -> Dict:
        """Very light DTO construction. Domain validation happens in UseCase.
        Returns a dict so adapters/tests don't depend on frameworks.
        """
        return {
            "electrode_mode": self.electrode_mode,
            "selection": sorted(self.selection),
            "params": dict(self.fields),
        }
    
    def build_well_params_map(self, wells: Iterable[WellId]) -> Dict[WellId, Dict[str, str]]:
        """Return a {well_id -> flat fields snapshot} map for the given wells."""
        out: Dict[WellId, Dict[str, str]] = {}
        for wid in wells:
            snap = self.well_params.get(wid)
            if snap:
                out[wid] = dict(snap)
        return out

    # Commands
    def cmd_apply_params(self) -> None:
        # Mark selected as configured would be handled by PlateVM externally.
        pass

    def cmd_start(self) -> None:
        if not self.selection:
            raise RuntimeError("No wells selected")
        plan = self.build_experiment_plan()
        if self.on_start_requested:
            self.on_start_requested(plan)

    def cmd_cancel_group(self) -> None:
        if self.on_cancel_group:
            self.on_cancel_group()


    def save_params_for(self, well_id: WellId, params: Dict[str, str]) -> None:
        """Persist a flat snapshot of the current fields for a well."""
        self.well_params[well_id] = dict(params or {})


    def get_params_for(self, well_id: WellId) -> Optional[Dict[str, str]]:
        """Return last saved params for a well, or None."""
        return self.well_params.get(well_id)
