"""Use case for constructing StorageMeta from settings and plan metadata."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any

from seva.domain.entities import PlanMeta
from seva.domain.ports import UseCaseError
from seva.domain.storage_meta import StorageMeta


@dataclass
class BuildStorageMeta:
    """Build normalized storage metadata from plan meta and settings."""

    def __call__(self, plan_meta: PlanMeta, settings: Any) -> StorageMeta:
        """Build ``StorageMeta`` used by download and persistence workflows.

        Args:
            plan_meta: Domain metadata from the prepared experiment plan.
            settings: Settings object exposing at least a ``results_dir`` value.

        Returns:
            StorageMeta: Typed metadata that downstream use cases can reuse.

        Side Effects:
            None.

        Call Chain:
            ``RunFlowPresenter.start_run`` -> ``BuildStorageMeta.__call__`` ->
            ``RunFlowCoordinator.start``.

        Usage:
            Constructed immediately before run start to freeze storage intent.

        Raises:
            UseCaseError: If ``plan_meta`` is not a ``PlanMeta`` instance.
        """
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
