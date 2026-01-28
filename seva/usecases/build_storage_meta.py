from __future__ import annotations

"""Use case for constructing StorageMeta from settings and plan metadata."""

from dataclasses import dataclass
from typing import Any

from seva.domain.entities import PlanMeta
from seva.domain.ports import UseCaseError
from seva.domain.storage_meta import StorageMeta


@dataclass
class BuildStorageMeta:
    """Build normalized storage metadata from plan meta and settings."""

    def __call__(self, plan_meta: PlanMeta, settings: Any) -> StorageMeta:
        if not isinstance(plan_meta, PlanMeta):
            raise UseCaseError("INVALID_PLAN_META", "Plan metadata is required.")
        results_dir = str(getattr(settings, "results_dir", "") or "").strip() or "."
        return StorageMeta(
            experiment=plan_meta.experiment,
            subdir=plan_meta.subdir,
            client_datetime=plan_meta.client_dt.value,
            results_dir=results_dir,
        )


__all__ = ["BuildStorageMeta"]
