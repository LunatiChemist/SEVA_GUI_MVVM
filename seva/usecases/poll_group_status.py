from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping

from seva.domain.entities import GroupId, GroupSnapshot

from seva.domain.ports import JobPort, RunGroupId, UseCaseError
from seva.domain.snapshot_normalizer import normalize_status


@dataclass
class PollGroupStatus:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> GroupSnapshot:
        """Poll the backend and return a normalized GroupSnapshot."""
        try:
            raw_snapshot = self.job_port.poll_group(run_group_id)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise UseCaseError("POLL_FAILED", str(exc)) from exc

        desired_group = str(run_group_id).strip()

        if isinstance(raw_snapshot, GroupSnapshot):
            snapshot = raw_snapshot
        else:
            payload: Dict[str, Any]
            if isinstance(raw_snapshot, Mapping):
                payload = dict(raw_snapshot)
            else:
                payload = {}

        # Ensure the group identifier travels with the snapshot before normalization.
            if desired_group:
                payload.setdefault("group", desired_group)
            else:
                payload.setdefault("group", run_group_id)

            snapshot = normalize_status(payload)

        if desired_group and str(snapshot.group) != desired_group:
            snapshot = replace(snapshot, group=GroupId(desired_group))

        return snapshot
