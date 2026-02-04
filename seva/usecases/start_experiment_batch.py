"""Use case for submitting experiment plans as backend jobs.

This orchestration step calls `JobPort.start_batch`, maps transport failures,
and returns run-group identifiers with per-box run mappings.
"""

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
        """Submit the prepared plan to the backend and return run identifiers.

        Args:
            plan: Fully validated domain plan produced by ``BuildExperimentPlan``.

        Returns:
            StartBatchResult: Group id and per-box run ids assigned by backend.

        Side Effects:
            Performs network I/O through ``JobPort.start_batch``.

        Call Chain:
            ``RunFlowCoordinator.start`` -> ``StartExperimentBatch.__call__`` ->
            ``JobPort.start_batch``.

        Usage:
            First adapter-facing step in the experiment execution workflow.

        Raises:
            UseCaseError: Propagated directly or produced through error mapping.
        """
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
