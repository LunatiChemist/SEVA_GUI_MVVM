from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

from seva.domain.ports import JobPort, UseCaseError, RunGroupId


@dataclass
class StartExperimentBatch:
    job_port: JobPort

    def __call__(self, plan: Dict) -> Tuple[RunGroupId, Dict[str, str]]:
        """
        Start a batch using a JobRequest-ready plan.
        Expected plan keys:
          - selection: List[WellId] (configured wells)
          - well_params_map: Dict[WellId, Dict[str,str]] (per-well snapshots incl. run_* flags)
          - (optional) folder_name, tia_gain, sampling_interval, make_plot, group_id
        """
        try:
            if not plan.get("selection"):
                raise ValueError("Start plan has no wells (selection is empty).")
            if not plan.get("well_params_map"):
                raise ValueError(
                    "Start plan has no per-well parameters (well_params_map is missing)."
                )

            run_group_id, subruns = self.job_port.start_batch(plan)
            return run_group_id, subruns
        except Exception as e:
            raise UseCaseError("START_FAILED", str(e))
