"""Use case for cancelling an entire run group.

The use case delegates cancellation to `JobPort` and normalizes transport
errors through shared error-mapping helpers.
"""

from __future__ import annotations
from dataclasses import dataclass
from ..domain.ports import JobPort, UseCaseError, RunGroupId
from ..usecases.error_mapping import map_api_error


@dataclass
class CancelGroup:
    """Use-case callable that cancels a run group.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> None:
        try:
            self.job_port.cancel_group(run_group_id)
        except Exception as e:
            raise map_api_error(
                e,
                default_code="CANCEL_FAILED",
                default_message="Cancel failed.",
            )
