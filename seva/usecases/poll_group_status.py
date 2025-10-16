from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

from seva.domain.ports import JobPort, UseCaseError, RunGroupId


@dataclass
class PollGroupStatus:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> Dict:
        """Attach server-side progress metrics to the poll snapshot."""
        run_info: Dict[str, Dict[str, Optional[int]]] = {}
        try:
            snap = self.job_port.poll_group(run_group_id)
            boxes = snap.get("boxes", {}) or {}
            all_boxes_terminal = bool(boxes)

            for _, meta in boxes.items():
                runs = meta.get("runs") or []
                statuses: list[str] = []

                if not runs:
                    all_boxes_terminal = False
                    continue

                for run in runs:
                    run_id = run.get("run_id")
                    status = str(run.get("status") or "queued").lower()
                    statuses.append(status)

                    if run_id:
                        run_info[run_id] = {
                            "progress_pct": run.get("progress_pct"),
                            "remaining_s": run.get("remaining_s"),
                        }

                statuses_set = {s for s in statuses if s}
                has_incomplete = any(s in {"queued", "running"} for s in statuses_set)
                all_terminal_box = bool(runs) and not has_incomplete and statuses_set.issubset(
                    {"done", "failed"}
                )

                if not all_terminal_box:
                    all_boxes_terminal = False

            well_rows = []
            for row in snap.get("wells", []):
                if len(row) < 5:
                    continue
                wid, state, progress_value, err, subrun = row[:5]
                info = run_info.get(subrun) or {}
                progress_pct = info.get("progress_pct")
                if progress_pct is None:
                    progress_pct = progress_value
                remaining_s = info.get("remaining_s")
                well_rows.append((wid, state, progress_pct, err, subrun, remaining_s))

            snap["wells"] = well_rows
            snap["all_done"] = bool(boxes) and all_boxes_terminal
            return snap
        except Exception as exc:
            raise UseCaseError("POLL_FAILED", str(exc))
