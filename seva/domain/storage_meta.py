from __future__ import annotations

"""Typed storage metadata used to build download paths and registry entries."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class StorageMeta:
    """Normalized storage metadata for a run group."""

    experiment: str
    subdir: Optional[str]
    client_datetime: datetime
    results_dir: str

    def __post_init__(self) -> None:
        if not isinstance(self.experiment, str) or not self.experiment.strip():
            raise ValueError("StorageMeta.experiment must be a non-empty string.")
        cleaned = self.subdir.strip() if isinstance(self.subdir, str) else None
        object.__setattr__(self, "subdir", cleaned or None)
        if not isinstance(self.results_dir, str) or not self.results_dir.strip():
            raise ValueError("StorageMeta.results_dir must be a non-empty string.")


__all__ = ["StorageMeta"]
