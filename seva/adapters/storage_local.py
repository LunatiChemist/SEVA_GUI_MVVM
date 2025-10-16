from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from seva.domain.ports import StoragePort


class StorageLocal(StoragePort):
    """Local filesystem storage for layouts and user settings (JSON)."""

    _FLAG_DEFAULTS: Tuple[str, ...] = (
        "run_cv",
        "run_dc",
        "run_ac",
        "run_eis",
        "run_lsv",
        "run_cdl",
        "eval_cdl",
    )

    def __init__(self, root_dir: str = ".") -> None:
        self.root = Path(root_dir)

    # ---- Layouts (JSON) ----
    def save_layout(self, name: str, payload: Dict) -> Path:
        path = self._layout_path(name)
        normalized = self._normalize_payload_for_dump(payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                normalized,
                fh,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        return path

    def load_layout(self, name: str | Path) -> Dict:
        path = self._layout_path(name)
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        well_params_map: Dict[str, Dict[str, Any]] = {}
        raw_map = raw.get("well_params_map")
        if isinstance(raw_map, dict):
            for raw_wid, snapshot in raw_map.items():
                wid = str(raw_wid)
                well_params_map[wid] = self._hydrate_snapshot(snapshot)
        selection = self._normalize_selection(raw.get("selection"), well_params_map.keys())
        return {"selection": selection, "well_params_map": well_params_map}

    # ---- User settings (JSON) ----
    def load_user_settings(self) -> Optional[Dict]:
        path = self.root / "user_settings.json"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def save_user_settings(self, payload: Dict) -> None:
        path = self.root / "user_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix="user_settings_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_fh:
                json.dump(payload, tmp_fh, ensure_ascii=False, indent=2)
                tmp_fh.flush()
                os.fsync(tmp_fh.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except FileNotFoundError:
                    pass

    def _layout_path(self, name: str | Path) -> Path:
        """Resolve layout filename with enforced layout_ prefix and .json suffix."""
        candidate = Path(name)
        if candidate.is_absolute():
            return candidate
        parent = candidate.parent if candidate.parent != Path(".") else Path()
        raw_name = candidate.name
        if not raw_name:
            raise ValueError("Layout name must not be empty.")
        if raw_name.startswith("layout_") and candidate.suffix.lower() == ".json":
            filename = raw_name
        else:
            stem = candidate.stem if candidate.suffix else raw_name
            if not stem.startswith("layout_"):
                stem = f"layout_{stem}"
            filename = f"{stem}.json"
        return self.root / parent / filename

    def _normalize_payload_for_dump(self, payload: Dict) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Layout payload must be a dict.")
        selection_raw = payload.get("selection") or []
        selection = self._coerce_selection(selection_raw)
        raw_map = payload.get("well_params_map")
        if not isinstance(raw_map, dict):
            raise ValueError("Layout payload must contain well_params_map dict.")
        prepared_map: Dict[str, Any] = {}
        for raw_wid, snapshot in raw_map.items():
            wid = str(raw_wid)
            prepared_map[wid] = self._prepare_snapshot_for_dump(snapshot)
        for wid in prepared_map:
            if wid not in selection:
                selection.append(wid)
        return {"selection": selection, "well_params_map": prepared_map}

    def _normalize_selection(self, selection: Any, known_wells) -> list[str]:
        normalized = self._coerce_selection(selection)
        for wid in known_wells:
            if wid not in normalized:
                normalized.append(wid)
        return normalized

    @staticmethod
    def _coerce_selection(selection: Any) -> list[str]:
        normalized: list[str] = []
        if isinstance(selection, (list, tuple, set)):
            for item in selection:
                wid = str(item)
                if wid not in normalized:
                    normalized.append(wid)
        elif isinstance(selection, str):
            normalized.append(selection)
        return normalized

    @staticmethod
    def _is_flag_key(key: Any) -> bool:
        return isinstance(key, str) and (key.startswith("run_") or key == "eval_cdl")

    def _prepare_snapshot_for_dump(self, snapshot: Any) -> Any:
        """Split snapshot into fields/flags for persistence (legacy: flat dict)."""
        if not isinstance(snapshot, dict):
            return snapshot
        fields: Dict[str, Any] = {}
        flags: Dict[str, Any] = {}
        for key, value in snapshot.items():
            (flags if self._is_flag_key(key) else fields)[key] = value
        return {"fields": fields, "flags": flags}

    def _hydrate_snapshot(self, payload: Any) -> Dict[str, Any]:
        """Merge persisted payload back into a flat snapshot with default flags."""
        snapshot: Dict[str, Any] = {}
        if isinstance(payload, dict):
            if "fields" in payload or "flags" in payload:
                fields = payload.get("fields")
                if isinstance(fields, dict):
                    snapshot.update(fields)
                flags = payload.get("flags")
                if isinstance(flags, dict):
                    snapshot.update(flags)
            else:
                snapshot.update(payload)
        for flag in self._FLAG_DEFAULTS:
            if flag not in snapshot:
                snapshot[flag] = "0"
        return snapshot
