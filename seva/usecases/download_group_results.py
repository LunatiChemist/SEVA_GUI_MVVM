from __future__ import annotations
from dataclasses import dataclass
from ..domain.ports import JobPort, UseCaseError, RunGroupId


@dataclass
class DownloadGroupResults:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId, target_dir: str) -> str:
        try:
            return self.job_port.download_group_zip(run_group_id, target_dir)
        except Exception as e:
            raise UseCaseError("DOWNLOAD_FAILED", str(e))
