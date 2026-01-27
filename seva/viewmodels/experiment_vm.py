from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Iterable, Tuple, cast
from ..domain import WellPlan, WellId, ModeName
from ..domain.params import ModeParams, CVParams, ACParams
from ..domain.util import normalize_mode_name

# Keep for filtering form fields for copy/paste
_MODE_CONFIG: Dict[str, Dict[str, object]] = {
    "CV": {
        "prefixes": ("cv.",),
        "flags": ("run_cv",),
        "extra": (),
        "clipboard_attr": "clipboard_cv",
    },
    # Shared DC/AC form fields live under "ea.*".
    # For the clipboard we still keep DC/AC together,
    # but on paste we write separate modes ("DC" / "AC").
    "DCAC": {
        "prefixes": ("ea.",),
        "flags": ("run_dc", "run_ac"),
        "extra": ("control_mode", "ea.target"),  # <-- target explizit aufnehmen
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

_MODE_BUILDERS: Dict[str, type[ModeParams]] = {
    "CV": CVParams,
    "AC": ACParams,
    # TODO: register additional mode parameter builders when modes are implemented.
}

@dataclass
class ExperimentVM:
    """Form/clipboard state and per-well params (grouped by modes).

    - `fields`: flat live form store (filled by the view via on_change)
    - `well_params`: persisted snapshots *per well*, grouped by modes
    - `clipboard_*`: flat mode-specific subsets from `fields`
    - `build_well_params_map()`: returns flat snapshots for domain/plan
    """

    # Signals (optional)
    on_start_requested: Optional[Callable[[Dict], None]] = None
    on_cancel_group: Optional[Callable[[], None]] = None

    # UI/global
    electrode_mode: str = "3E"  # "2E" | "3E"
    editing_well: Optional[WellId] = None
    selection: Set[WellId] = field(default_factory=set)

    # Persistence: grouped params per well (only active modes present)
    well_params: Dict[WellId, Dict[ModeName, Dict[str, str]]] = field(default_factory=dict)

    # Live-Form-Store (flat)
    fields: Dict[str, str] = field(default_factory=dict)

    # Clipboards (flat)
    clipboard_cv: Dict[str, str] = field(default_factory=dict)
    clipboard_dcac: Dict[str, str] = field(default_factory=dict)
    clipboard_cdl: Dict[str, str] = field(default_factory=dict)
    clipboard_eis: Dict[str, str] = field(default_factory=dict)

    # ---------- Live form API ----------
    def set_field(self, field_id: str, value: str) -> None:
        self.fields[field_id] = value

    def set_selection(self, wells: Set[WellId]) -> None:
        self.selection = set(wells)

    def set_electrode_mode(self, mode: str) -> None:
        if mode not in ("2E", "3E"):
            raise ValueError("Invalid ElectrodeMode")
        self.electrode_mode = mode

    # ---------- Copy helpers ----------
    def build_mode_snapshot_for_copy(self, mode: str) -> Dict[str, str]:
        """Filter the current form store `fields` to the fields of a mode."""
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

        # Keep the target mode active when copying
        for flag in flags:
            snapshot[flag] = "1"

        return snapshot

    # ---------- Persistenz (gruppiert) ----------
    def save_params_for(self, well_id: WellId, params: Dict[str, str]) -> None:
        """Persist *grouped* params per well. Only active modes are saved."""
        grouped = self._group_fields_by_mode(params or {})
        if grouped:
            self.well_params[well_id] = grouped
        else:
            # Nichts aktiv -> Eintrag entfernen
            self.well_params.pop(well_id, None)

    def get_params_for(self, well_id: WellId) -> Optional[Dict[str, str]]:
        """Return a flat mapping for the view (including reconstructed flags)."""
        raw = self.well_params.get(well_id)
        if not raw:
            return None
        return self._flatten_for_view(raw)

    def clear_params_for(self, well_id: WellId) -> None:
        self.well_params.pop(well_id, None)

    # ---------- Plan/Domain ----------
    def build_experiment_plan(self) -> Dict:
        """Light DTO (not domain-specific)."""
        return {
            "electrode_mode": self.electrode_mode,
            "selection": sorted(self.selection),
            "params": dict(self.fields),
        }
    
    def well_ids(self) -> List[WellId]:
        data = self.well_params
        return list(data.keys())


    def mode_names_for_well(self,
        well_id: WellId,
    ) -> List[ModeName]:
        data = self.well_params
        return list(data[well_id].keys())


    def modes_dict_for_well(self, well_id: WellId) -> Dict[ModeName, ModeParams]:
        """
        Return typed mode parameters for a well.
        If a mode is registered in MODE_BUILDERS, its class is used,
        otherwise it falls back to the base ModeParams class.
        """
        modes_raw: Mapping[ModeName, Mapping[str, Any]] = self.well_params[well_id]
        out: Dict[ModeName, ModeParams] = {}

        for mode_name, cfg in modes_raw.items():
            raw_mode = str(mode_name)
            builder = _MODE_BUILDERS.get(raw_mode, ModeParams)
            try:
                params = builder.from_form(cfg)  # type: ignore[arg-type]
            except (NotImplementedError, AttributeError, TypeError):
                # Fallback: initialize directly with flags
                params = builder(flags=dict(cfg))  # type: ignore[arg-type]

            normalized_mode = normalize_mode_name(raw_mode)
            out[normalized_mode] = params

        return out

    def build_well_plan_map(
        self,
        wells: Optional[Iterable[WellId]] = None,
    ) -> List[WellPlan]:
        """Compiles Wellplans for each Well"""
        well_ids = list(wells)
        plans_per_well = []
        for wid in well_ids:
            plan = WellPlan(well=wid,
                            modes=self.mode_names_for_well(wid),
                            params_by_mode=self.modes_dict_for_well(wid))
            plans_per_well.append(plan)
        return plans_per_well

    # ---------- Commands ----------
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

        prefixes = cast(Tuple[str, ...], config["prefixes"])
        flags = cast(Tuple[str, ...], config["flags"])
        extras = cast(Tuple[str, ...], config["extra"])

        def _is_mode_field(fid: str) -> bool:
            return fid in flags or fid in extras or any(fid.startswith(p) for p in prefixes)

        snapshot = (
            self.build_mode_snapshot_for_copy(mode)
            if source_snapshot is None
            else {fid: val for fid, val in source_snapshot.items() if _is_mode_field(fid)}
        )
        if not snapshot:
            return

        for flag in flags:
            snapshot[flag] = "1"
        clipboard.update(snapshot)

    def cmd_paste_mode(self, mode: str, well_ids: Iterable[WellId]) -> None:
        mode_key = (mode or "").upper()
        config = _MODE_CONFIG.get(mode_key)
        if not config:
            raise ValueError(f"Unsupported mode: {mode}")
        clipboard_attr = cast(str, config["clipboard_attr"])
        clipboard: Dict[str, str] = getattr(self, clipboard_attr)
        if not clipboard:
            return

        for wid in well_ids:
            grouped = dict(self.well_params.get(wid, {}))  # copy

            if mode_key == "CV":
                sub = {k: v for k, v in clipboard.items() if k.startswith("cv.")}
                if sub:
                    grouped["CV"] = sub
                else:
                    grouped.pop("CV", None)

            elif mode_key == "DCAC":
                # DC separat
                if self._is_truthy(clipboard.get("run_dc")):
                    grouped["DC"] = self._extract_ea_params(
                        clipboard,
                        include_frequency=False,
                    )
                else:
                    grouped.pop("DC", None)
                # AC separat
                if self._is_truthy(clipboard.get("run_ac")):
                    grouped["AC"] = self._extract_ea_params(
                        clipboard,
                        include_frequency=True,
                    )
                else:
                    grouped.pop("AC", None)

            elif mode_key == "CDL":
                sub = {k: v for k, v in clipboard.items() if k.startswith("cdl.")}
                if sub:
                    grouped["CDL"] = sub
                else:
                    grouped.pop("CDL", None)

            elif mode_key == "EIS":
                sub = {k: v for k, v in clipboard.items() if k.startswith("eis.")}
                if sub:
                    grouped["EIS"] = sub
                else:
                    grouped.pop("EIS", None)

            self.well_params[wid] = grouped

    # ---------- Helpers ----------
    @staticmethod
    def _is_truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _group_fields_by_mode(self, flat: Dict[str, str]) -> Dict[ModeName, Dict[str, str]]:
        """Convert live form into a grouped snapshot. Only active modes."""
        run_cv  = self._is_truthy(flat.get("run_cv"))
        run_dc  = self._is_truthy(flat.get("run_dc"))
        run_ac  = self._is_truthy(flat.get("run_ac"))
        run_eis = self._is_truthy(flat.get("run_eis"))
        eval_cdl = self._is_truthy(flat.get("eval_cdl"))

        grouped: Dict[ModeName, Dict[str, str]] = {}

        if run_cv:
            grouped["CV"] = {k: v for k, v in flat.items() if k.startswith("cv.")}

        if run_dc:
            dc = self._extract_ea_params(flat, include_frequency=False)
            if dc:
                grouped["DC"] = dc

        if run_ac:
            ac = self._extract_ea_params(flat, include_frequency=True)
            if ac:
                grouped["AC"] = ac

        if eval_cdl:
            cdl = {k: v for k, v in flat.items() if k.startswith("cdl.")}
            if cdl:
                grouped["CDL"] = cdl

        if run_eis:
            eis = {k: v for k, v in flat.items() if k.startswith("eis.")}
            if eis:
                grouped["EIS"] = eis

        return grouped

    def _flatten_for_view(self, grouped: Dict[ModeName, Dict[str, str]]) -> Dict[str, str]:
        """Unpack grouped snapshot for the view (including checkmarks)."""
        flat: Dict[str, str] = {}

        # CV
        if "CV" in grouped:
            flat.update(grouped["CV"])
        # DC/AC: For the shared ea.* fields we prefer AC (if present).
        if "AC" in grouped:
            flat.update(grouped["AC"])
        elif "DC" in grouped:
            flat.update(grouped["DC"])
        # CDL & EIS
        if "CDL" in grouped:
            flat.update(grouped["CDL"])
        if "EIS" in grouped:
            flat.update(grouped["EIS"])

        # Reconstruct flags for the view
        flat["run_cv"]   = "1" if "CV"  in grouped else "0"
        flat["run_dc"]   = "1" if "DC"  in grouped else "0"
        flat["run_ac"]   = "1" if "AC"  in grouped else "0"
        flat["eval_cdl"] = "1" if "CDL" in grouped else "0"
        flat["run_eis"]  = "1" if "EIS" in grouped else "0"

        return flat

    @staticmethod
    def _extract_ea_params(
        source: Mapping[str, str],
        *,
        include_frequency: bool,
    ) -> Dict[str, str]:
        params = {k: v for k, v in source.items() if k.startswith("ea.")}
        if not include_frequency:
            params.pop("ea.frequency_hz", None)
        if "control_mode" in source:
            params["control_mode"] = source["control_mode"]
        if "ea.target" in source:
            params["ea.target"] = source["ea.target"]
        return params
