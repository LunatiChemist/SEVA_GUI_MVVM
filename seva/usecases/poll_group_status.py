from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

from seva.domain.ports import JobPort, UseCaseError, RunGroupId


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


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

            for box_id, meta in boxes.items():
                runs = meta.get("runs") or []
                statuses: list[str] = []
                progresses: list[int] = []

                for run in runs:
                    run_id = run.get("run_id")
                    status = str(run.get("status") or "queued").lower()
                    statuses.append(status)

                    progress_pct = _coerce_int(run.get("progress_pct"), default=0)
                    remaining_s = _coerce_optional_int(run.get("remaining_s"))

                    run["progress_pct"] = progress_pct
                    run["progress"] = progress_pct
                    run["remaining_s"] = remaining_s
                    progresses.append(progress_pct)

                    if run_id:
                        run_info[run_id] = {
                            "progress_pct": progress_pct,
                            "remaining_s": remaining_s,
                        }

                if progresses:
                    meta["progress"] = int(round(sum(progresses) / len(progresses)))
                else:
                    meta["progress"] = 0

                statuses_set = {s for s in statuses if s}
                has_incomplete = any(s in {"queued", "running"} for s in statuses_set)
                all_terminal_box = bool(runs) and not has_incomplete and statuses_set.issubset(
                    {"done", "failed"}
                )

                if all_terminal_box:
                    meta["phase"] = "Failed" if "failed" in statuses_set else "Done"
                elif "running" in statuses_set:
                    meta["phase"] = "Running"
                elif "queued" in statuses_set and "running" not in statuses_set:
                    meta["phase"] = "Queued"
                elif "failed" in statuses_set and "running" not in statuses_set:
                    meta["phase"] = "Failed"
                else:
                    meta["phase"] = meta.get("phase") or "Mixed"

                if not all_terminal_box:
                    all_boxes_terminal = False

            well_rows = []
            for row in snap.get("wells", []):
                if len(row) < 5:
                    continue
                wid, state, _, err, subrun = row[:5]
                info = run_info.get(subrun) or {}
                progress_pct = info.get("progress_pct", 0) or 0
                remaining_s = info.get("remaining_s")
                well_rows.append((wid, state, progress_pct, err, subrun, remaining_s))

            snap["wells"] = well_rows
            snap["all_done"] = bool(boxes) and all_boxes_terminal
            return snap
        except Exception as exc:
            raise UseCaseError("POLL_FAILED", str(exc))
