"""Use case for cancelling an entire run group.

The use case delegates cancellation to `JobPort` and normalizes transport
errors through shared error-mapping helpers.
"""

from __future__ import annotations
from dataclasses import dataclass
from seva.domain.ports import JobPort, UseCaseError, RunGroupId
from seva.usecases.error_mapping import map_api_error


@dataclass
class CancelGroup:
    """Use-case callable that cancels a run group.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> None:
        """Cancel all runs that belong to a backend group identifier.

        Args:
            run_group_id: Group id returned from ``StartExperimentBatch``.

        Returns:
            None.

        Side Effects:
            Sends a cancellation request through ``JobPort``.

        Call Chain:
            UI cancel action -> presenter/controller -> ``CancelGroup.__call__`` ->
            ``JobPort.cancel_group``.

        Usage:
            Used by "Cancel Group" actions to stop every run in the group.

        Raises:
            UseCaseError: Adapter failures are mapped to domain error codes.
        """
        try:
            self.job_port.cancel_group(run_group_id)
        except Exception as e:
            raise map_api_error(
                e,
                default_code="CANCEL_FAILED",
                default_message="Cancel failed.",
            )
