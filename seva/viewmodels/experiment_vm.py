from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Set, Iterable
from ..domain import WellId, ModeName
from ..domain.modes import ModeRegistry

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

    # Mode registry (centralized rules/labels/builders)
    mode_registry: ModeRegistry = field(default_factory=ModeRegistry.default)

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
        return self.mode_registry.filter_fields(mode, self.fields)

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

    def clear_all_params(self) -> None:
        self.well_params.clear()

    # ---------- Commands ----------
    def cmd_copy_mode(
        self,
        mode: str,
        well_id: WellId,
        source_snapshot: Optional[Dict[str, str]] = None,
    ) -> None:
        rule = self.mode_registry.rule_for(mode)
        clipboard_attr = rule.clipboard_attr
        clipboard: Dict[str, str] = getattr(self, clipboard_attr)
        clipboard.clear()

        snapshot = (
            self.build_mode_snapshot_for_copy(mode)
            if source_snapshot is None
            else {
                fid: val
                for fid, val in source_snapshot.items()
                if self.mode_registry.is_mode_field(mode, fid)
            }
        )
        if not snapshot:
            return

        for flag in rule.flags:
            snapshot[flag] = "1"
        clipboard.update(snapshot)

    def cmd_paste_mode(self, mode: str, well_ids: Iterable[WellId]) -> None:
        mode_key = (mode or "").upper()
        rule = self.mode_registry.rule_for(mode_key)
        clipboard_attr = rule.clipboard_attr
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
