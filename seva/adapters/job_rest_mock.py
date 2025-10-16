from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from seva.domain.ports import BoxId, JobPort, RunGroupId


@dataclass
class JobRestMock(JobPort):
    """Offline substitute for ``JobRestAdapter`` with deterministic responses."""

    def __post_init__(self) -> None:
        self._groups: Dict[RunGroupId, Dict[BoxId, List[str]]] = {}
        self._runs: Dict[Tuple[RunGroupId, BoxId, str], Dict[str, Any]] = {}

    # ---------- JobPort ----------

    def start_batch(
        self, plan: Dict[str, Any]
    ) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        jobs = list(plan.get("jobs") or [])
        if not jobs:
            raise ValueError("start_batch: missing 'jobs' in plan")

        group_id: RunGroupId = plan.get("group_id") or str(uuid4())
        grouped: Dict[BoxId, List[str]] = {}
        self._groups[group_id] = {}

        for job in jobs:
            box: Optional[BoxId] = job.get("box")
            if not box:
                raise ValueError("start_batch: job requires 'box'")
            run_id = str(job.get("run_name") or f"{box}-run-{uuid4().hex[:8]}")

            grouped.setdefault(box, []).append(run_id)
            self._groups[group_id].setdefault(box, []).append(run_id)
            self._runs[(group_id, box, run_id)] = {
                "run_id": run_id,
                "status": "running",
                "started_at": None,
            }

        return group_id, grouped

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        for key, data in list(self._runs.items()):
            if key[0] != run_group_id:
                continue
            data["status"] = "cancelled"

    def poll_group(self, run_group_id: RunGroupId) -> Dict[str, Any]:
        boxes: Dict[BoxId, Dict[str, Any]] = {}
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
        key = (run_group_id, box_id, run_id)
        if key not in self._runs:
            self._runs[key] = {"run_id": run_id}
        self._runs[key]["status"] = status
        self._runs[key]["started_at"] = started_at
