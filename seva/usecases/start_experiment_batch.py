from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from seva.domain.entities import ExperimentPlan
from seva.domain.ports import BoxId, JobPort, RunGroupId, UseCaseError
from seva.usecases.error_mapping import map_api_error


@dataclass
class StartBatchResult:
    """Aggregate outcome for a batch start attempt."""

    run_group_id: RunGroupId | None
    per_box_runs: Dict[BoxId, List[str]]


@dataclass
class StartExperimentBatch:
    """Use-case orchestrating job submission for an experiment plan."""

    job_port: JobPort

    def __call__(self, plan: ExperimentPlan) -> StartBatchResult:
        try:
            run_group_id, per_box_runs = self.job_port.start_batch(plan)
        except UseCaseError:
            raise
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="START_FAILED",
                default_message="Start failed.",
            ) from exc

        return StartBatchResult(
            run_group_id=run_group_id,
            per_box_runs=per_box_runs,
        )
