from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from seva.domain.ports import JobPort, UseCaseError, RunGroupId, BoxId
from seva.usecases.group_registry import set_planned_duration

@dataclass
class StartExperimentBatch:
    job_port: JobPort

    def __call__(self, plan: Dict) -> Tuple[RunGroupId, Dict[str, str]]:
        """Validate plan, start per box via JobPort, and record planned durations."""
        try:
            # Extract planned duration once from params (mode dependent)
            params = plan.get("params") or {}
            planned: Optional[int] = None
            # Convention: params.total_duration_s defines planned runtime (int seconds)
            if "total_duration_s" in params:
                try:
                    planned = int(params["total_duration_s"])
                except Exception:
                    planned = None

            run_group_id, subruns = self.job_port.start_batch(plan)

            # Store per box planned duration for progress calc later
            for box in subruns.keys():
                set_planned_duration(run_group_id, box, planned)

            return run_group_id, subruns
        except Exception as e:
            raise UseCaseError("START_FAILED", str(e))
