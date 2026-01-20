from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from seva.domain.runs_registry import RunEntry, RunsRegistry
from .status_format import registry_status_label


@dataclass
class RunRow:
    group_id: str
    name: str
    status: str
    progress: str
    boxes: str
    started_at: str
    download_path: str


class RunsVM:
    """
    Lightweight view-model for the runs overview panel.

    Exposes registry entries as plain rows and keeps track of the currently
    active group for downstream views.
    """

    def __init__(self, registry: RunsRegistry) -> None:
        self._registry = registry
        self.active_group_id: Optional[str] = None

    def set_active_group(self, group_id: Optional[str]) -> None:
        self.active_group_id = group_id

    def rows(self) -> List[RunRow]:
        rows: List[RunRow] = [self._to_row(entry) for entry in self._registry.all_entries()]
        rows.sort(key=lambda row: row.started_at, reverse=True)
        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _to_row(self, entry: RunEntry) -> RunRow:
        name = entry.name or entry.group_id
        status = self._format_status(entry)
        progress = self._format_progress(entry.last_snapshot)
        boxes = ",".join(entry.boxes) if entry.boxes else "-"
        started_at = self._format_dt(entry.created_at)
        download_path = entry.download.path or ""
        return RunRow(
            group_id=entry.group_id,
            name=name,
            status=status,
            progress=progress,
            boxes=boxes,
            started_at=started_at,
            download_path=download_path,
        )

    def _format_status(self, entry: RunEntry) -> str:
        return registry_status_label(entry.status, downloaded=entry.download.done)

    def _format_progress(self, snapshot: Optional[Dict[str, Any]]) -> str:
        if not snapshot:
            return "-"

        pct = snapshot.get("progress_pct") or snapshot.get("percent")
        if isinstance(pct, (int, float)):
            return f"{int(pct)}%"

        runs = snapshot.get("runs") or []
        try:
            items = list(runs.values()) if isinstance(runs, dict) else list(runs)
        except Exception:
            items = []
        total = len(items)
        if total == 0:
            return "-"

        done_states = {"done", "failed", "cancelled"}
        done = 0
        for item in items:
            state = (item.get("state") or item.get("phase") or "").lower() if isinstance(item, dict) else ""
            if state in done_states or item.get("done") is True:
                done += 1
        return f"{int(done * 100 / total)}%"

    def _format_dt(self, iso_ts: str) -> str:
        if not iso_ts:
            return ""
        try:
            if iso_ts.endswith("Z"):
                dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(iso_ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_ts or ""


__all__ = ["RunRow", "RunsVM"]
