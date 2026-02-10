"""Use case for cancelling selected runs grouped by box.

This module deduplicates run identifiers and delegates per-run cancellation to
the job adapter port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from seva.domain.ports import JobPort
from seva.usecases.error_mapping import map_api_error


@dataclass
class CancelRuns:
    """Use-case callable that cancels explicit run identifiers.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    job_port: JobPort

    def __call__(self, box_to_run_ids: Dict[str, List[str]]) -> None:
        """Cancel selected runs grouped by box identifier.

        Args:
            box_to_run_ids: Mapping of box id to one or more run ids.

        Returns:
            None.

        Side Effects:
            Issues one cancellation call per unique run id.

        Call Chain:
            End-selection presenter action -> ``CancelRuns.__call__`` ->
            ``CancelRuns._cancel_for_box`` -> ``JobPort.cancel_run``.

        Usage:
            Stops only selected wells/runs instead of a full group cancel.

        Raises:
            UseCaseError: Adapter failures are mapped via ``map_api_error``.
        """
        for box, runs in box_to_run_ids.items():
            box_id = str(box or "").strip()
            if not box_id:
                continue
            self._cancel_for_box(box_id, runs or [])

    def _cancel_for_box(self, box_id: str, runs: Iterable[str]) -> None:
        """Cancel deduplicated runs for one box.

        Args:
            box_id: Box identifier key used by the backend.
            runs: Candidate run ids collected from UI selection state.

        Returns:
            None.

        Side Effects:
            Calls ``JobPort.cancel_run`` for each unique non-empty run id.

        Raises:
            UseCaseError: If any adapter cancellation call fails.
        """
        seen: Set[str] = set()
        for run_id in runs:
            run_id_str = str(run_id or "").strip()
            if not run_id_str or run_id_str in seen:
                continue
            seen.add(run_id_str)
            try:
                self.job_port.cancel_run(box_id, run_id_str)
            except Exception as exc:
                raise map_api_error(
                    exc,
                    default_code="CANCEL_RUN_FAILED",
                    default_message="Cancel run failed.",
                ) from exc
