from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..domain.entities import BoxSnapshot, GroupSnapshot, RunStatus, WellId


@dataclass
class ProgressVM:
    """Owns polling state and aggregates status for RunOverview & ChannelActivity.

    - Timer/backoff handled by Infra later; here we expose hooks and state bags
    - Receives consolidated status (e.g., from PollGroupStatus use case)
    - Translates to View DTOs
    """

    on_update_run_overview: Optional[Callable[[Dict], None]] = (
        None  # Dict with box & well rows
    )
    on_update_channel_activity: Optional[Callable[[Dict], None]] = (
        None  # WellId -> status
    )

    run_group_id: Optional[str] = None
    last_snapshot: Optional[GroupSnapshot] = None

    def set_run_group(self, run_id: Optional[str]) -> None:
        self.run_group_id = run_id

    def apply_snapshot(self, snapshot: GroupSnapshot) -> None:
        """Consume the latest GroupSnapshot and fan it out to the views."""
        if not isinstance(snapshot, GroupSnapshot):
            raise TypeError("ProgressVM.apply_snapshot requires a GroupSnapshot.")

        self.last_snapshot = snapshot
        self.run_group_id = str(snapshot.group)

        well_rows, activity_map, runs_by_box = self._derive_well_rows(snapshot)
        boxes_map = self._derive_box_rows(snapshot, runs_by_box)

        dto = {
            "boxes": boxes_map,
            "wells": well_rows,
            "activity": activity_map,
        }
        if self.on_update_run_overview:
            self.on_update_run_overview(dto)
        if self.on_update_channel_activity:
            self.on_update_channel_activity(activity_map)

    # ------------------------------------------------------------------
    # DTO builders
    # ------------------------------------------------------------------
    def _derive_well_rows(
        self, snapshot: GroupSnapshot
    ) -> Tuple[List[Tuple[str, str, Optional[float], Optional[int], str, str]], Dict[str, str], Dict[str, List[Tuple[str, RunStatus]]]]:
        """
        Prepare table rows + channel activity from the domain snapshot.

        Returns (rows, activity_map, runs_grouped_by_box).
        """
        rows: List[Tuple[str, str, Optional[float], Optional[int], str, str]] = []
        activity: Dict[str, str] = {}
        grouped: Dict[str, List[Tuple[str, RunStatus]]] = {}

        ordered_runs: Sequence[Tuple[WellId, RunStatus]] = sorted(
            snapshot.runs.items(), key=lambda item: item[0].value
        )
        for well_id, run in ordered_runs:
            well_token = str(well_id)
            phase_label = self._phase_label(run.phase)
            progress_pct = float(run.progress.value) if run.progress else None
            remaining_s = int(run.remaining_s.value) if run.remaining_s else None
            error_text = run.error or ""
            run_id_token = str(run.run_id)

            rows.append(
                (well_token, phase_label, progress_pct, remaining_s, error_text, run_id_token)
            )
            activity[well_token] = self._activity_label(run)

            box_token = self._extract_box_prefix(well_id)
            if box_token:
                grouped.setdefault(box_token, []).append((well_token, run))

        return rows, activity, grouped

    def _derive_box_rows(
        self,
        snapshot: GroupSnapshot,
        runs_by_box: Dict[str, List[Tuple[str, RunStatus]]],
    ) -> Dict[str, Dict[str, object]]:
        """
        Compose per-box header data sourced from snapshot aggregates + run details.
        """
        boxes: Dict[str, Dict[str, object]] = {}

        for box_id, box_snapshot in snapshot.boxes.items():
            box_token = str(box_id)
            runs = runs_by_box.get(box_token, [])
            boxes[box_token] = self._box_payload(box_token, box_snapshot, runs)

        for box_token, runs in runs_by_box.items():
            if box_token not in boxes:
                boxes[box_token] = self._box_payload(box_token, None, runs)

        return dict(sorted(boxes.items()))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _box_payload(
        self,
        box_token: str,
        box_snapshot: Optional[BoxSnapshot],
        runs: List[Tuple[str, RunStatus]],
    ) -> Dict[str, object]:
        progress_value = self._box_progress(box_snapshot, runs)
        remaining_value = self._box_remaining(box_snapshot, runs)
        phase_label = self._aggregate_box_phase(runs)
        subruns = self._collect_box_run_ids(runs)

        payload: Dict[str, object] = {
            "phase": phase_label,
            "progress": progress_value,
            "subrun": subruns,
        }
        if remaining_value is not None:
            payload["remaining"] = remaining_value
        return payload

    @staticmethod
    def _collect_box_run_ids(runs: List[Tuple[str, RunStatus]]) -> List[str]:
        seen: List[str] = []
        for well_token, run in sorted(runs, key=lambda item: item[0]):
            run_id = str(run.run_id).strip()
            if run_id and run_id not in seen:
                seen.append(run_id)
        return seen

    def _aggregate_box_phase(self, runs: List[Tuple[str, RunStatus]]) -> str:
        if not runs:
            return "Idle"

        phases = {self._phase_key(run.phase) for _, run in runs if run.phase}
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
        phase_key = next(iter(phases))
        return self._phase_label(phase_key)

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
        key = self._phase_key(run.phase)
        if key in {"failed", "error"}:
            return "Error"
        if key in {"canceled", "cancelled"}:
            return "Canceled"
        return self._phase_label(key)

    def _phase_label(self, phase: str) -> str:
        key = self._phase_key(phase)
        mapping = {
            "failed": "Failed",
            "error": "Error",
            "running": "Running",
            "queued": "Queued",
            "done": "Done",
            "canceled": "Canceled",
            "cancelled": "Canceled",
            "idle": "Idle",
        }
        if not key:
            return "Idle"
        if key in mapping:
            return mapping[key]
        cleaned = key.replace("_", " ").replace("-", " ")
        return cleaned.title()

    @staticmethod
    def _phase_key(phase: str) -> str:
        return (phase or "").strip().lower()

    @staticmethod
    def _extract_box_prefix(well_id: WellId) -> Optional[str]:
        token = ""
        for ch in str(well_id):
            if ch.isalpha():
                token += ch
            else:
                break
        return token or None
