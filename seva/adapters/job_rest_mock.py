"""In-memory ``JobPort`` test double for offline workflows.

This adapter mimics the run lifecycle exposed by ``JobRestAdapter`` without
network I/O so use cases can be validated deterministically.

Dependencies:
    - Domain ``ExperimentPlan`` and ``JobPort`` contracts.

Call context:
    - Unit/integration tests and local development scenarios that avoid REST API.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from seva.domain.entities import ExperimentPlan
from seva.domain.ports import BoxId, JobPort, RunGroupId
from seva.domain.util import well_id_to_box


@dataclass
class JobRestMock(JobPort):
    """Deterministic in-memory implementation of ``JobPort``."""

    def __post_init__(self) -> None:
        """Initialize in-memory run-group registries."""
        self._groups: Dict[RunGroupId, Dict[BoxId, List[str]]] = {}
        self._runs: Dict[Tuple[RunGroupId, BoxId, str], Dict[str, Any]] = {}
        self._group_started: Dict[RunGroupId, float] = {}

    # ---------- JobPort ----------

    def start_batch(
        self, plan: ExperimentPlan
    ) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        """Create synthetic run IDs for each planned well.

        Args:
            plan: Typed experiment plan from plan-building use case.

        Returns:
            Tuple of ``(run_group_id, runs_by_box)`` matching ``JobPort`` contract.

        Raises:
            TypeError: If ``plan`` is not an ``ExperimentPlan``.
            ValueError: If well identifiers are missing/invalid.

        Side Effects:
            Stores run/group records in mock in-memory state.
        """
        if not isinstance(plan, ExperimentPlan):
            raise TypeError("start_batch requires an ExperimentPlan.")

        group_id: RunGroupId = str(plan.meta.group_id)
        grouped: Dict[BoxId, List[str]] = {}
        self._groups[group_id] = {}
        self._group_started[group_id] = time.time()

        for well_plan in plan.wells:
            well_id = str(well_plan.well).strip()
            if not well_id:
                raise ValueError("Experiment plan contains an empty well identifier.")

            box_id = well_id_to_box(well_id)
            if not box_id:
                raise ValueError(f"Invalid well identifier: {well_id}")
            box: BoxId = box_id
            run_id = f"{box}-run-{uuid4().hex[:8]}"

            # Mirror adapter expectations by ensuring params serialize without errors.
            for params in (well_plan.params_by_mode or {}).values():
                params.to_payload()

            grouped.setdefault(box, []).append(run_id)
            self._groups[group_id].setdefault(box, []).append(run_id)
            self._runs[(group_id, box, run_id)] = {
                "run_id": run_id,
                "status": "running",
                "started_at": None,
            }

        return group_id, grouped

    def cancel_run(self, box_id: BoxId, run_id: str) -> None:
        """Mark a single mock run as cancelled.

        Args:
            box_id: Box identifier containing the run.
            run_id: Run identifier to cancel.
        """
        for (group_id, box, rid), data in self._runs.items():
            if box == box_id and rid == run_id:
                data["status"] = "cancelled"

    def cancel_runs(self, box_to_run_ids: Dict[BoxId, List[str]]) -> None:
        """Cancel multiple runs grouped by box.

        Args:
            box_to_run_ids: Mapping of box IDs to run IDs.
        """
        for box_id, run_ids in box_to_run_ids.items():
            for run_id in run_ids or []:
                self.cancel_run(box_id, run_id)

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        """Cancel every run belonging to a run group.

        Args:
            run_group_id: Group identifier to cancel.
        """
        for key, data in list(self._runs.items()):
            if key[0] != run_group_id:
                continue
            data["status"] = "cancelled"

    def poll_group(self, run_group_id: RunGroupId) -> Dict[str, Any]:
        """Return normalized polling snapshot from in-memory run state.

        Args:
            run_group_id: Group identifier to poll.

        Returns:
            Snapshot dictionary compatible with ``PollGroupStatus`` expectations.
        """
        boxes: Dict[BoxId, Dict[str, Any]] = {}
        started = self._group_started.get(run_group_id, time.time())
        elapsed = max(0.0, time.time() - started)
        progress = min(100.0, (elapsed / 60.0) * 100.0)
        for box, runs in self._groups.get(run_group_id, {}).items():
            entries: List[Dict[str, Any]] = []
            statuses = set()
            for run_id in runs:
                record = self._runs.get((run_group_id, box, run_id), {})
                status = str(record.get("status", "queued")).lower()
                statuses.add(status)
                entries.append(
                    {
                        "run_id": record.get("run_id", run_id),
                        "status": status,
                        "started_at": record.get("started_at"),
                        "progress_pct": progress,
                    }
                )
            if not statuses:
                phase = "queued"
            elif len(statuses) == 1:
                phase = next(iter(statuses))
            else:
                phase = "mixed"
            boxes[box] = {"runs": entries, "phase": phase.capitalize()}

        return {"boxes": boxes, "wells": []}

    def download_group_zip(self, run_group_id: RunGroupId, target_dir: str) -> str:
        """Create empty placeholder ZIP files for each run.

        Args:
            run_group_id: Group identifier to materialize.
            target_dir: Root output directory.

        Returns:
            Output directory path containing group/box ZIP placeholders.

        Side Effects:
            Creates directories and zero-byte ``.zip`` files on disk.
        """
        out_dir = os.path.join(target_dir, str(run_group_id))
        os.makedirs(out_dir, exist_ok=True)
        for box, runs in self._groups.get(run_group_id, {}).items():
            box_dir = os.path.join(out_dir, box)
            os.makedirs(box_dir, exist_ok=True)
            for run_id in runs:
                path = os.path.join(box_dir, f"{run_id}.zip")
                if not os.path.exists(path):
                    with open(path, "wb") as fh:
                        fh.write(b"")
        return out_dir

    # ---------- Test helpers ----------

    def set_run_status(
        self,
        run_group_id: RunGroupId,
        box_id: BoxId,
        run_id: str,
        *,
        status: str,
        started_at: Optional[str] = None,
    ) -> None:
        """Mutate a mock run entry for test assertions.

        Args:
            run_group_id: Group identifier.
            box_id: Box identifier.
            run_id: Run identifier.
            status: New status token.
            started_at: Optional ISO timestamp string.

        Side Effects:
            Creates the run record when missing and updates stored fields.
        """
        key = (run_group_id, box_id, run_id)
        if key not in self._runs:
            self._runs[key] = {"run_id": run_id}
        self._runs[key]["status"] = status
        self._runs[key]["started_at"] = started_at
