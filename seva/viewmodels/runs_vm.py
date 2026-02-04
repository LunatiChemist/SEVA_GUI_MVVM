"""Runs overview view model backed by `RunsRegistry`.

It projects registry entries into lightweight table rows for the runs panel and
tracks the currently active run group selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from seva.domain.runs_registry import RunEntry, RunsRegistry
from .status_format import registry_status_label


@dataclass
class RunRow:
    """Display row model for the runs overview table.
    
    Attributes:
        Fields are consumed by views and controller orchestration glue.
    """
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

        progress_values: List[float] = []
        boxes = snapshot.get("boxes")
        if isinstance(boxes, dict):
            for meta in boxes.values():
                if not isinstance(meta, dict):
                    continue
                value = meta.get("progress")
                if value is None:
                    value = meta.get("progress_pct") or meta.get("percent")
                if isinstance(value, (int, float)):
                    progress_values.append(float(value))

        runs = snapshot.get("runs") or []
        if isinstance(runs, dict):
            items = list(runs.values())
        elif isinstance(runs, (list, tuple)):
            items = list(runs)
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            value = item.get("progress")
            if value is None:
                value = item.get("progress_pct") or item.get("percent")
            if isinstance(value, (int, float)):
                progress_values.append(float(value))

        if progress_values:
            avg = sum(progress_values) / len(progress_values)
            return f"{int(avg)}%"

        items = items
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
        if iso_ts.endswith("Z"):
            dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d %H:%M")


__all__ = ["RunRow", "RunsVM"]
