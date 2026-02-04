"""Progress dashboard view model for run and channel activity panels.

It transforms `GroupSnapshot` and registry state into UI-ready rows and emits
update callbacks consumed by run overview and channel activity views.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..domain.entities import BoxId, BoxSnapshot, GroupSnapshot, RunStatus, WellId
from ..domain.runs_registry import RunsRegistry
from ..domain.snapshot_normalizer import normalize_status
from ..domain.util import well_id_to_box
from .status_format import phase_key, phase_label
from ..domain.device_activity import DeviceActivitySnapshot

# -- top of file / next to the other type aliases:
WellRow = Tuple[str, str, str, str, Optional[float], str, str, str]
#            |    |    |    |     |            |    |    |
#            well phase cur  next  progress     rem  err  subrun
BoxRow = Tuple[str, Optional[float], str]
ActivityMap = Dict[str, str]


@dataclass
class ProgressVM:
    """Owns polling state and aggregates status for RunOverview & ChannelActivity."""

    on_update_run_overview: Optional[Callable[[Dict], None]] = None
    on_update_channel_activity: Optional[Callable[[ActivityMap], None]] = None

    run_group_id: Optional[str] = None
    active_group_id: Optional[str] = None
    last_snapshot: Optional[GroupSnapshot] = None
    updated_at_label: str = ""

    def set_run_group(self, run_id: Optional[str]) -> None:
        self.run_group_id = run_id

    def set_active_group(self, group_id: Optional[str], registry: RunsRegistry) -> None:
        self.active_group_id = group_id
        if not group_id:
            return
        entry = registry.get(group_id)
        if not entry or not entry.last_snapshot:
            return

        snapshot_data = entry.last_snapshot
        if isinstance(snapshot_data, GroupSnapshot):
            self.apply_snapshot(snapshot_data)
            return

        if isinstance(snapshot_data, dict):
            rebuilt = self._snapshot_from_serialized(snapshot_data)
            if rebuilt:
                self.apply_snapshot(rebuilt)

    def apply_snapshot(self, snapshot: GroupSnapshot) -> None:
        """Consume the latest GroupSnapshot and fan it out to the views."""
        if not isinstance(snapshot, GroupSnapshot):
            raise TypeError("ProgressVM.apply_snapshot requires a GroupSnapshot.")

        self.last_snapshot = snapshot
        self.run_group_id = str(snapshot.group)
        self.active_group_id = str(snapshot.group)

        well_rows, activity_map, runs_by_box = self._build_well_state(snapshot)
        box_rows = self.derive_box_rows(snapshot, runs_by_box)
        boxes_payload = self._compose_box_payload(snapshot, runs_by_box)

        self.updated_at_label = self._current_time_label()

        dto = {
            "boxes": boxes_payload,
            "box_rows": box_rows,
            "wells": well_rows,
            "activity": activity_map,
            "updated_at": self.updated_at_label,
        }

        if self.on_update_run_overview:
            self.on_update_run_overview(dto)

    def apply_activity_snapshot(self, snapshot: GroupSnapshot) -> None:
        """Update only the channel activity matrix from a snapshot."""
        if not isinstance(snapshot, GroupSnapshot):
            raise TypeError("ProgressVM.apply_activity_snapshot requires a GroupSnapshot.")

        activity_map = self._build_activity_map(snapshot)
        self.updated_at_label = self._current_time_label()
        if self.on_update_channel_activity:
            self.on_update_channel_activity(activity_map)

    def apply_device_activity(self, snapshot: DeviceActivitySnapshot) -> None:
        if not isinstance(snapshot, DeviceActivitySnapshot):
            raise TypeError("ProgressVM.apply_device_activity requires a DeviceActivitySnapshot.")

        activity_map: ActivityMap = {
            entry.well_id: entry.status for entry in snapshot.entries
        }
        self.updated_at_label = self._current_time_label()
        if self.on_update_channel_activity:
            self.on_update_channel_activity(activity_map)

    # ------------------------------------------------------------------
    # Public DTO helpers
    # ------------------------------------------------------------------
    def derive_well_rows(self, snapshot: GroupSnapshot) -> List[WellRow]:
        """Return well table rows sorted by WellId (domain order).

        8-tuple per row (View-Spaltenreihenfolge):
        (well, phase, current_mode, next_modes, progress, remaining, error, subrun)
        """
        ordered_runs = sorted(snapshot.runs.items(), key=lambda item: item[0].value)
        rows: List[WellRow] = []
        for well_id, run in ordered_runs:
            phase_text = phase_label(run.phase)

            progress_val = float(run.progress.value) if run.progress is not None else None
            remaining_s = int(run.remaining_s.value) if run.remaining_s is not None else None
            remaining_label = self.fmt_remaining(remaining_s)

            # direct from Domain RunStatus (new in entities):
            cur = run.current_mode or ""
            nxt = ", ".join(run.remaining_modes) if run.remaining_modes else ""

            rows.append((
                str(well_id),
                phase_text,
                cur,
                nxt,
                progress_val,
                remaining_label,
                (run.error or "").strip(),
                str(run.run_id),
            ))
        return rows

    def _snapshot_from_serialized(self, payload: Dict[str, Union[str, Dict, List]]) -> Optional[GroupSnapshot]:
        """Rebuild a GroupSnapshot from a serialized registry payload."""
        return normalize_status(payload)

    def derive_box_rows(
        self,
        snapshot: GroupSnapshot,
        runs_by_box: Optional[Dict[str, List[Tuple[str, RunStatus]]]] = None,
    ) -> List[BoxRow]:
        """Return per-box summary rows (box_id, avg progress, max remaining label)."""
        runs_map = runs_by_box or self._group_runs_by_box(snapshot)
        boxes = self._collect_box_tokens(snapshot, runs_map)
        snapshot_by_token = {
            str(box_id): box_snapshot for box_id, box_snapshot in snapshot.boxes.items()
        }
        rows: List[BoxRow] = []
        for box_token in boxes:
            runs = runs_map.get(box_token, [])
            box_snapshot = snapshot_by_token.get(box_token)
            remaining_s = self._box_remaining(box_snapshot, runs)
            rows.append(
                (
                    box_token,
                    self._box_progress(box_snapshot, runs),
                    self.fmt_remaining(remaining_s),
                )
            )
        return rows

    def map_selection_to_runs(
        self, selection: Sequence[Union[WellId, str]]
    ) -> Dict[str, List[str]]:
        """Map selected wells to their run identifiers grouped by Box."""
        if not selection or not self.last_snapshot:
            return {}

        selected_tokens = {str(item).strip() for item in selection if str(item).strip()}
        if not selected_tokens:
            return {}

        grouped: Dict[str, List[str]] = {}
        for well_id, status in self.last_snapshot.runs.items():
            well_token = str(well_id)
            if well_token not in selected_tokens:
                continue
            run_token = str(status.run_id).strip()
            if not run_token:
                continue
            box_token = self._extract_box_prefix(well_id)
            if not box_token:
                continue
            bucket = grouped.setdefault(box_token, [])
            if run_token not in bucket:
                bucket.append(run_token)

        sorted_grouped: Dict[str, List[str]] = {}
        for box_token in sorted(grouped):
            sorted_grouped[box_token] = sorted(grouped[box_token])
        return sorted_grouped

    @staticmethod
    def fmt_remaining(seconds: Optional[int]) -> str:
        """Format remaining seconds as m:ss or h:mm:ss."""
        if seconds is None:
            return ""
        total = int(seconds)
        if total < 0:
            total = 0
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_well_state(
        self, snapshot: GroupSnapshot
    ) -> Tuple[List[WellRow], ActivityMap, Dict[str, List[Tuple[str, RunStatus]]]]:
        rows = self.derive_well_rows(snapshot)
        activity = self._build_activity_map(snapshot)
        runs_by_box = self._group_runs_by_box(snapshot)
        return rows, activity, runs_by_box

    def _compose_box_payload(
        self,
        snapshot: GroupSnapshot,
        runs_by_box: Dict[str, List[Tuple[str, RunStatus]]],
    ) -> Dict[str, Dict[str, object]]:
        payload: Dict[str, Dict[str, object]] = {}
        boxes = self._collect_box_tokens(snapshot, runs_by_box)
        snapshot_by_token = {
            str(box_id): box_snapshot for box_id, box_snapshot in snapshot.boxes.items()
        }
        for box_token in boxes:
            runs = runs_by_box.get(box_token, [])
            box_snapshot = snapshot_by_token.get(box_token)
            remaining_s = self._box_remaining(box_snapshot, runs)
            payload[box_token] = {
                "phase": self._aggregate_box_phase(runs),
                "progress": self._box_progress(box_snapshot, runs),
                "remaining": remaining_s,
                "remaining_label": self.fmt_remaining(remaining_s),
                "subrun": self._collect_box_run_ids(runs),
            }
        return payload

    @staticmethod
    def _collect_box_tokens(
        snapshot: GroupSnapshot, runs_by_box: Dict[str, List[Tuple[str, RunStatus]]]
    ) -> List[str]:
        tokens = {str(box_id) for box_id in snapshot.boxes.keys()}
        tokens.update(runs_by_box.keys())
        return sorted(tokens)

    def _group_runs_by_box(
        self, snapshot: GroupSnapshot
    ) -> Dict[str, List[Tuple[str, RunStatus]]]:
        grouped: Dict[str, List[Tuple[str, RunStatus]]] = {}
        for well_id, run in snapshot.runs.items():
            box_token = self._extract_box_prefix(well_id)
            if not box_token:
                continue
            grouped.setdefault(box_token, []).append((str(well_id), run))
        for runs in grouped.values():
            runs.sort(key=lambda item: item[0])
        return grouped

    def _build_activity_map(self, snapshot: GroupSnapshot) -> ActivityMap:
        activity: ActivityMap = {}
        for well_id, run in snapshot.runs.items():
            activity[str(well_id)] = self._activity_label(run)
        return activity

    def _current_time_label(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime())

    def _aggregate_box_phase(self, runs: List[Tuple[str, RunStatus]]) -> str:
        if not runs:
            return "Idle"

        phases = {phase_key(run.phase) for _, run in runs if run.phase}
        if {"failed", "error"} & phases:
            return "Error"
        if "running" in phases:
            return "Running"
        if "queued" in phases:
            return "Queued"
        if {"canceled", "cancelled"} & phases:
            return "Canceled"
        if phases == {"done"}:
            return "Done"
        if not phases:
            return "Idle"
        phase_token = next(iter(phases))
        return phase_label(phase_token)

    @staticmethod
    def _collect_box_run_ids(runs: List[Tuple[str, RunStatus]]) -> List[str]:
        seen: List[str] = []
        for well_token, run in sorted(runs, key=lambda item: item[0]):
            run_id = str(run.run_id).strip()
            if run_id and run_id not in seen:
                seen.append(run_id)
        return seen

    @staticmethod
    def _box_progress(
        box_snapshot: Optional[BoxSnapshot], runs: List[Tuple[str, RunStatus]]
    ) -> float:
        if box_snapshot and box_snapshot.progress is not None:
            return float(box_snapshot.progress.value)
        progress_values = [
            float(run.progress.value) for _, run in runs if run.progress is not None
        ]
        if not progress_values:
            return 0.0
        return sum(progress_values) / len(progress_values)

    @staticmethod
    def _box_remaining(
        box_snapshot: Optional[BoxSnapshot], runs: List[Tuple[str, RunStatus]]
    ) -> Optional[int]:
        if box_snapshot and box_snapshot.remaining_s is not None:
            return int(box_snapshot.remaining_s.value)
        remaining_values = [
            int(run.remaining_s.value) for _, run in runs if run.remaining_s is not None
        ]
        if not remaining_values:
            return None
        return max(remaining_values)

    def _activity_label(self, run: RunStatus) -> str:
        if run.error:
            return "Error"
        key = phase_key(run.phase)
        if key in {"failed", "error"}:
            return "Error"
        if key in {"canceled", "cancelled"}:
            return "Canceled"
        return phase_label(key)

    @staticmethod
    def _extract_box_prefix(well_id: Union[WellId, str]) -> Optional[str]:
        return well_id_to_box(str(well_id))
