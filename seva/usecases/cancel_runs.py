from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from ..domain.ports import JobPort


@dataclass
class CancelRuns:
    job_port: JobPort

    def __call__(self, box_to_run_ids: Dict[str, List[str]]) -> None:
        for box, runs in box_to_run_ids.items():
            box_id = str(box or "").strip()
            if not box_id:
                continue
            self._cancel_for_box(box_id, runs or [])

    def _cancel_for_box(self, box_id: str, runs: Iterable[str]) -> None:
        seen: Set[str] = set()
        for run_id in runs:
            run_id_str = str(run_id or "").strip()
            if not run_id_str or run_id_str in seen:
                continue
            seen.add(run_id_str)
            self.job_port.cancel_run(box_id, run_id_str)
