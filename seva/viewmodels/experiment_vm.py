from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Set, Iterable, Tuple, cast

WellId = str

_MODE_CONFIG: Dict[str, Dict[str, object]] = {
    "CV": {
        "prefixes": ("cv.",),
        "flags": ("run_cv",),
        "extra": (),
        "clipboard_attr": "clipboard_cv",
    },
    "DCAC": {
        "prefixes": ("ea.",),
        "flags": ("run_dc", "run_ac"),
        "extra": ("control_mode",),
        "clipboard_attr": "clipboard_dcac",
    },
    "CDL": {
        "prefixes": ("cdl.",),
        "flags": ("eval_cdl",),
        "extra": (),
        "clipboard_attr": "clipboard_cdl",
    },
    "EIS": {
        "prefixes": ("eis.",),
        "flags": ("run_eis",),
        "extra": (),
        "clipboard_attr": "clipboard_eis",
    },
}


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
    clipboard_cv: Dict[str, str] = field(default_factory=dict)
    clipboard_dcac: Dict[str, str] = field(default_factory=dict)
    clipboard_cdl: Dict[str, str] = field(default_factory=dict)
    clipboard_eis: Dict[str, str] = field(default_factory=dict)

    def build_mode_snapshot_for_copy(self, mode: str) -> Dict[str, str]:
        mode_key = (mode or "").upper()
        config = _MODE_CONFIG.get(mode_key)
        if not config:
            raise ValueError(f"Unsupported mode: {mode}")

        prefixes = cast(Tuple[str, ...], config["prefixes"])
        flags = cast(Tuple[str, ...], config["flags"])
        extras = cast(Tuple[str, ...], config["extra"])

        def _is_mode_field(fid: str) -> bool:
            return fid in flags or fid in extras or any(fid.startswith(p) for p in prefixes)

        snapshot = {fid: val for fid, val in self.fields.items() if _is_mode_field(fid)}

        # Ensure the mode-specific run flags are active when the snapshot is pasted.
        for flag in flags:
            snapshot[flag] = "1"

        return snapshot

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

    def cmd_copy_mode(
        self,
        mode: str,
        well_id: WellId,
        source_snapshot: Optional[Dict[str, str]] = None,
    ) -> None:
        mode_key = (mode or "").upper()
        config = _MODE_CONFIG.get(mode_key)
        if not config:
            raise ValueError(f"Unsupported mode: {mode}")
        clipboard_attr = cast(str, config["clipboard_attr"])
        clipboard: Dict[str, str] = getattr(self, clipboard_attr)
        clipboard.clear()

        if source_snapshot is not None:
            # Copy now relies on the live form fields instead of persisted params.
            clipboard.update(source_snapshot)
            return

        snap = self.get_params_for(well_id) or {}
        if not snap:
            return

        prefixes = cast(Tuple[str, ...], config["prefixes"])
        flags = cast(Tuple[str, ...], config["flags"])
        extras = cast(Tuple[str, ...], config["extra"])

        def _is_mode_field(fid: str) -> bool:
            return fid in flags or fid in extras or any(fid.startswith(p) for p in prefixes)

        for fid, val in snap.items():
            if _is_mode_field(fid):
                clipboard[fid] = val

        # Always activate the mode in the clipboard to ensure pastes enable it.
        for flag in flags:
            clipboard[flag] = "1"

    def cmd_paste_mode(self, mode: str, well_ids: Iterable[WellId]) -> None:
        mode_key = (mode or "").upper()
        config = _MODE_CONFIG.get(mode_key)
        if not config:
            raise ValueError(f"Unsupported mode: {mode}")
        clipboard_attr = cast(str, config["clipboard_attr"])
        clipboard: Dict[str, str] = getattr(self, clipboard_attr)
        if not clipboard:
            return

        prefixes = cast(Tuple[str, ...], config["prefixes"])
        flags = cast(Tuple[str, ...], config["flags"])
        extras = cast(Tuple[str, ...], config["extra"])

        def _is_mode_field(fid: str) -> bool:
            return fid in flags or fid in extras or any(fid.startswith(p) for p in prefixes)

        for wid in well_ids:
            if not wid:
                continue
            current = dict(self.well_params.get(wid, {}))
            for fid in [k for k in list(current.keys()) if _is_mode_field(k)]:
                current.pop(fid, None)
            current.update(clipboard)
            self.well_params[wid] = current

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

    def clear_params_for(self, well_id: WellId) -> None:
        """Forget stored parameters (including mode flags) for the given well."""
        self.well_params.pop(well_id, None)
