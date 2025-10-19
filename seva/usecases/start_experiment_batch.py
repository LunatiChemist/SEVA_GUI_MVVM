from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from seva.domain.entities import ExperimentPlan
from seva.domain.ports import BoxId, JobPort, RunGroupId, UseCaseError, WellId


@dataclass
class WellValidationResult:
    """Structured summary for per-well validation feedback."""

    well_id: WellId
    box_id: BoxId
    mode: str
    ok: bool
    errors: List[Dict[str, object]]
    warnings: List[Dict[str, object]]


@dataclass
class StartBatchResult:
    """Aggregate outcome for a batch start attempt."""

    run_group_id: RunGroupId | None
    per_box_runs: Dict[BoxId, List[str]]
    started_wells: List[str]


@dataclass
class StartExperimentBatch:
    """Use-case orchestrating job submission for an experiment plan."""

    job_port: JobPort

    def __call__(self, plan: ExperimentPlan) -> StartBatchResult:
        if not isinstance(plan, ExperimentPlan):
            raise TypeError("StartExperimentBatch requires an ExperimentPlan instance.")

        started_wells: List[str] = []
        for well_plan in plan.wells:
            well_id = str(well_plan.well).strip()
            if not well_id:
                raise UseCaseError("START_FAILED", "Experiment plan contains an empty well identifier.")

            try:
                # Trigger serialization early so adapter failures surface as use-case errors.
                well_plan.params.to_payload()
            except Exception as exc:  # pragma: no cover - defensive normalization
                raise UseCaseError("START_FAILED", f"{well_id}: {exc}") from exc

            started_wells.append(well_id)

        try:
            run_group_id, per_box_runs = self.job_port.start_batch(plan)
        except UseCaseError:
            raise
        except Exception as exc:
            raise UseCaseError("START_FAILED", str(exc)) from exc

        return StartBatchResult(
            run_group_id=run_group_id,
            per_box_runs=per_box_runs,
            started_wells=started_wells,
        )
