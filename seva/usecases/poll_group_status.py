from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

from seva.domain.entities import GroupSnapshot

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

        payload: Mapping[str, object]
        if isinstance(raw_snapshot, Mapping):
            payload = dict(raw_snapshot)
        else:
            payload = {}

        # Ensure the group identifier travels with the snapshot before normalization.
        payload.setdefault("group", run_group_id)
        return normalize_status(payload)
