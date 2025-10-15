from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional

from ..domain.ports import JobPort, RunGroupId, UseCaseError
from ..utils.download_paths import build_group_root


@dataclass
class GroupStorageHint:
    """Metadata describing the expected storage folder for a run group."""

    experiment_name: Optional[str] = None
    client_datetime: Optional[str] = None
    subdir: Optional[str] = None


@dataclass
class DownloadGroupResults:
    job_port: JobPort

    def __call__(
        self,
        run_group_id: RunGroupId,
        target_dir: str,
        *,
        storage_hint: Optional[GroupStorageHint] = None,
    ) -> str:
        """Download group archives and return the absolute storage root path."""
        try:
            source_dir = self.job_port.download_group_zip(run_group_id, target_dir)
        except Exception as exc:
            raise UseCaseError("DOWNLOAD_FAILED", str(exc))

        destination = self._resolve_destination(target_dir, run_group_id, storage_hint)
        source_abs = os.path.abspath(source_dir)
        if source_abs == destination:
            return destination

        try:
            self._relocate_group_contents(source_abs, destination)
        except Exception as exc:
            raise UseCaseError("DOWNLOAD_FAILED", str(exc))
        return destination

    def _resolve_destination(
        self,
        target_dir: str,
        run_group_id: RunGroupId,
        storage_hint: Optional[GroupStorageHint],
    ) -> str:
        """Compute the final group folder based on the provided storage hint."""
        hint = storage_hint or GroupStorageHint()
        return build_group_root(
            target_dir,
            experiment_name=hint.experiment_name,
            client_datetime=hint.client_datetime,
            subdir=hint.subdir,
            fallback_segment=run_group_id,
        )

    def _relocate_group_contents(self, source: str, destination: str) -> None:
        """Move the downloaded ZIP directory to the desired destination."""
        if not os.path.isdir(source):
            os.makedirs(destination, exist_ok=True)
            return

        parent = os.path.dirname(destination)
        if parent:
            os.makedirs(parent, exist_ok=True)

        if os.path.exists(destination):
            shutil.rmtree(destination)

        shutil.move(source, destination)
