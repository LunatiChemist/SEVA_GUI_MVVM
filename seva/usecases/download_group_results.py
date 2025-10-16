from __future__ import annotations

import os
from dataclasses import dataclass

from ..domain.ports import JobPort, RunGroupId, UseCaseError


@dataclass
class DownloadGroupResults:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId, target_dir: str) -> str:
        """Download group archives and return the absolute storage root path."""
        expected_root = os.path.join(target_dir, str(run_group_id))
        try:
            downloaded_path = self.job_port.download_group_zip(run_group_id, target_dir)
        except Exception as exc:
            raise UseCaseError("DOWNLOAD_FAILED", str(exc))

        resolved = os.path.abspath(downloaded_path)
        expected_root_abs = os.path.abspath(expected_root)

        if os.path.isdir(resolved):
            return resolved
        if os.path.isdir(expected_root_abs):
            return expected_root_abs

        # Fallback to the parent folder if adapter returned a file path.
        parent_dir = os.path.dirname(resolved)
        if parent_dir and os.path.isdir(parent_dir):
            return parent_dir

        return expected_root_abs
