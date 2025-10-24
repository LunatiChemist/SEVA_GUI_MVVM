from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set, Iterable, Tuple, cast

WellId = str
ModeName = str  # "CV" | "DC" | "AC" | "CDL" | "EIS"

# Beibehalten zur Filterung von Formularfeldern für Copy/Paste
_MODE_CONFIG: Dict[str, Dict[str, object]] = {
    "CV": {
        "prefixes": ("cv.",),
        "flags": ("run_cv",),
        "extra": (),
        "clipboard_attr": "clipboard_cv",
    },
    # Gemeinsame DC/AC-Formularfelder liegen unter "ea.*".
    # Für das Clipboard halten wir DC/AC weiterhin zusammen,
    # beim Paste schreiben wir aber getrennte Modi ("DC" / "AC").
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

_RUN_FLAG_KEYS: Tuple[str, ...] = (
    "run_cv",
    "run_dc",
    "run_ac",
    "run_eis",
    "eval_cdl",
)


@dataclass
class ExperimentVM:
    """Form-/Clipboard-State und per-Well-Params (gruppiert nach Modi).

    - `fields`: flacher Live-Form-Store (von der View via on_change befüllt)
    - `well_params`: persistierte Snapshots *pro Well*, gruppiert nach Modi
    - `clipboard_*`: flache mode-spezifische Subsets aus `fields`
    - `build_well_params_map()`: liefert für Domain/Plan flache Snapshots zurück
    """

    # Signals (optional)
    on_start_requested: Optional[Callable[[Dict], None]] = None
    on_cancel_group: Optional[Callable[[], None]] = None

    # UI/global
    electrode_mode: str = "3E"  # "2E" | "3E"
    editing_well: Optional[WellId] = None
    selection: Set[WellId] = field(default_factory=set)

    # Persistenz: pro Well gruppierte Params (nur aktivierte Modi vorhanden)
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
        """Filtert den aktuellen Formular-Store `fields` auf die Felder eines Modus."""
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

        # Beim Kopieren den Zielmodus aktiv halten
        for flag in flags:
            snapshot[flag] = "1"

        return snapshot

    # ---------- Persistenz (gruppiert) ----------
    def save_params_for(self, well_id: WellId, params: Dict[str, str]) -> None:
        """Persistiere *gruppierte* Params pro Well. Nur aktivierte Modi werden gespeichert."""
        grouped = self._group_fields_by_mode(params or {})
        if grouped:
            self.well_params[well_id] = grouped
        else:
            # Nichts aktiv -> Eintrag entfernen
            self.well_params.pop(well_id, None)

    def get_params_for(self, well_id: WellId) -> Optional[Dict[str, str]]:
        """Liefere flaches Mapping für die View (inkl. rekonstruierter Flags)."""
        raw = self.well_params.get(well_id)
        if not raw:
            # Backwards-Compat: alte flache Snapshots?
            legacy = cast(Optional[Dict[str, str]], None)
            if isinstance(raw, dict) and raw and all(isinstance(v, str) for v in raw.values()):
                legacy = cast(Dict[str, str], raw)
            if not legacy:
                return None
            grouped = self._group_fields_by_mode(legacy)
            self.well_params[well_id] = grouped
            return self._flatten_for_view(grouped)

        # raw ist gruppiert (ModeName -> Dict[str,str])
        return self._flatten_for_view(raw)

    def clear_params_for(self, well_id: WellId) -> None:
        self.well_params.pop(well_id, None)

    # ---------- Plan/Domain ----------
    def build_experiment_plan(self) -> Dict:
        """Light DTO (nicht Domain-spezifisch)."""
        return {
            "electrode_mode": self.electrode_mode,
            "selection": sorted(self.selection),
            "params": dict(self.fields),
        }

    def build_well_params_map(
        self,
        wells: Optional[Iterable[WellId]] = None,
    ) -> Dict[WellId, Dict[str, Any]]:
        """Übergabe an den PlanBuilder: flache Snapshots, wie bisher erwartet."""
        well_ids = list(wells) if wells is not None else list(self.well_params.keys())
        result: Dict[WellId, Dict[str, Any]] = {}

        for wid in well_ids:
            modes = self.well_params.get(wid) or {}
            if "CV" in modes:
                # Flatten wie vorher: cv.* + Flags (nur run_cv=1)
                flat: Dict[str, Any] = dict(modes["CV"])
                for flag in _RUN_FLAG_KEYS:
                    flat[flag] = "1" if flag == "run_cv" else "0"
                result[wid] = flat
                continue
            # TODO: Wenn Domain bereit: DC/AC/EIS/CDL ebenfalls flatten (analog zu CV).

        return result

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
                    dc = {k: v for k, v in clipboard.items() if k.startswith("ea.")}
                    dc.pop("ea.frequency_hz", None)  # DC braucht keine Frequenz
                    if "control_mode" in clipboard:
                        dc["control_mode"] = clipboard["control_mode"]
                    if "ea.target" in clipboard:
                        dc["ea.target"] = clipboard["ea.target"]
                    grouped["DC"] = dc
                else:
                    grouped.pop("DC", None)
                # AC separat
                if self._is_truthy(clipboard.get("run_ac")):
                    ac = {k: v for k, v in clipboard.items() if k.startswith("ea.")}
                    if "control_mode" in clipboard:
                        ac["control_mode"] = clipboard["control_mode"]
                    if "ea.target" in clipboard:
                        ac["ea.target"] = clipboard["ea.target"]
                    grouped["AC"] = ac
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
        """Live-Form in gruppierten Snapshot überführen. Nur aktivierte Modi."""
        run_cv  = self._is_truthy(flat.get("run_cv"))
        run_dc  = self._is_truthy(flat.get("run_dc"))
        run_ac  = self._is_truthy(flat.get("run_ac"))
        run_eis = self._is_truthy(flat.get("run_eis"))
        eval_cdl = self._is_truthy(flat.get("eval_cdl"))

        grouped: Dict[ModeName, Dict[str, str]] = {}

        if run_cv:
            grouped["CV"] = {k: v for k, v in flat.items() if k.startswith("cv.")}

        if run_dc:
            dc = {k: v for k, v in flat.items() if k.startswith("ea.")}
            dc.pop("ea.frequency_hz", None)  # DC ohne Frequenz
            if "control_mode" in flat:
                dc["control_mode"] = flat["control_mode"]
            if "ea.target" in flat:
                dc["ea.target"] = flat["ea.target"]
            if dc:
                grouped["DC"] = dc

        if run_ac:
            ac = {k: v for k, v in flat.items() if k.startswith("ea.")}
            if "control_mode" in flat:
                ac["control_mode"] = flat["control_mode"]
            if "ea.target" in flat:
                ac["ea.target"] = flat["ea.target"]
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
        """Gruppierten Snapshot für die View (inkl. Checkmarks) „entpacken“."""
        flat: Dict[str, str] = {}

        # CV
        if "CV" in grouped:
            flat.update(grouped["CV"])
        # DC/AC: Für die gemeinsamen ea.* Felder bevorzugen wir AC (falls vorhanden).
        if "AC" in grouped:
            flat.update(grouped["AC"])
        elif "DC" in grouped:
            flat.update(grouped["DC"])
        # CDL & EIS
        if "CDL" in grouped:
            flat.update(grouped["CDL"])
        if "EIS" in grouped:
            flat.update(grouped["EIS"])

        # Flags für die View rekonstruieren
        flat["run_cv"]   = "1" if "CV"  in grouped else "0"
        flat["run_dc"]   = "1" if "DC"  in grouped else "0"
        flat["run_ac"]   = "1" if "AC"  in grouped else "0"
        flat["eval_cdl"] = "1" if "CDL" in grouped else "0"
        flat["run_eis"]  = "1" if "EIS" in grouped else "0"

        return flat
