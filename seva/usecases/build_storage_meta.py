from __future__ import annotations

"""Use case for constructing StorageMeta from settings and plan inputs."""

from dataclasses import dataclass
from typing import Any, Mapping

from seva.domain.storage_meta import StorageMeta


@dataclass
class BuildStorageMeta:
    """Placeholder for storage metadata construction."""

    def __call__(self, settings: Any, plan_meta: Mapping[str, Any]) -> StorageMeta:
        raise NotImplementedError("BuildStorageMeta is not implemented yet.")


__all__ = ["BuildStorageMeta"]
