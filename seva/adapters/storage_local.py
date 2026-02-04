"""Filesystem-backed `StoragePort` implementation for layouts and settings.

Use cases and controllers rely on this adapter for JSON persistence while keeping
file I/O outside view models and domain logic.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict

from seva.domain.ports import StoragePort
from seva.viewmodels.settings_vm import default_settings_payload


class StorageLocal(StoragePort):
    """Local filesystem storage for layouts and user settings (JSON)."""

    def __init__(self, root_dir: str = ".") -> None:
        self.root = Path(root_dir)

    # ---- Layouts (JSON) ----
    def save_layout(self, name: str, payload: Dict) -> Path:
        path = self._layout_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                payload,
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
        well_params_map = dict(raw.get("well_params_map") or {})
        selection = list(raw.get("selection") or [])
        return {"selection": selection, "well_params_map": well_params_map}

    # ---- User settings (JSON) ----
    def load_user_settings(self) -> Dict:
        path = self.root / "user_settings.json"
        if not path.exists():
            return default_settings_payload()
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise ValueError("User settings payload must be a JSON object.")
        return raw

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
