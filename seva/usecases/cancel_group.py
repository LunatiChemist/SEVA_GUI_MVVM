from __future__ import annotations
from dataclasses import dataclass
from ..domain.ports import JobPort, UseCaseError, RunGroupId


@dataclass
class CancelGroup:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> None:
        try:
            self.job_port.cancel_group(run_group_id)
        except Exception as e:
            raise UseCaseError("CANCEL_FAILED", str(e))
