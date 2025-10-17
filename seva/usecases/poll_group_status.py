from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

from seva.domain.ports import JobPort, UseCaseError, RunGroupId


TERMINAL_STATUSES = {"done", "failed", "canceled", "cancelled"}


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    try:
        text = str(value).strip()
        if not text:
            return None
        if "." in text:
            return int(round(float(text)))
        return int(text)
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

            for _, meta in boxes.items():
                runs = meta.get("runs") or []
                statuses: list[str] = []
                remaining_candidates: list[int] = []
                progress_values: list[int] = []

                if not runs:
                    all_boxes_terminal = False
                    meta["remaining_s"] = None
                    meta["progress"] = None
                    continue

                for run in runs:
                    run_id = run.get("run_id")
                    status = str(run.get("status") or "queued").lower()
                    statuses.append(status)

                    progress_pct = _to_int(run.get("progress_pct"))
                    remaining_s = _to_int(run.get("remaining_s"))

                    if progress_pct is not None:
                        progress_values.append(progress_pct)
                        run["progress_pct"] = progress_pct
                    elif "progress_pct" in run:
                        run["progress_pct"] = None

                    if remaining_s is not None:
                        run["remaining_s"] = remaining_s
                    elif "remaining_s" in run:
                        run["remaining_s"] = None

                    if status not in TERMINAL_STATUSES and remaining_s is not None:
                        remaining_candidates.append(remaining_s)

                    if run_id:
                        run_info[run_id] = {
                            "progress_pct": progress_pct,
                            "remaining_s": remaining_s,
                        }

                statuses_set = {s for s in statuses if s}
                has_incomplete = any(s not in TERMINAL_STATUSES for s in statuses_set)
                all_terminal_box = (
                    bool(runs)
                    and not has_incomplete
                    and statuses_set.issubset(TERMINAL_STATUSES)
                )

                if not all_terminal_box:
                    all_boxes_terminal = False

                if progress_values:
                    avg_progress = round(sum(progress_values) / len(progress_values))
                    meta["progress"] = int(avg_progress)
                else:
                    meta["progress"] = None

                meta["remaining_s"] = max(remaining_candidates) if remaining_candidates else None

            well_rows = []
            for row in snap.get("wells", []):
                if len(row) < 5:
                    continue
                if len(row) >= 6:
                    wid, state, progress_value, remaining_value, err, subrun = row[:6]
                else:
                    wid, state, progress_value, err, subrun = row[:5]
                    remaining_value = None

                info = run_info.get(subrun) or {}
                progress_pct = info.get("progress_pct")
                if progress_pct is None:
                    coerced_progress = _to_int(progress_value)
                    progress_pct = (
                        coerced_progress if coerced_progress is not None else progress_value
                    )

                remaining_s = info.get("remaining_s")
                if remaining_s is None:
                    remaining_s = _to_int(remaining_value)

                well_rows.append((wid, state, progress_pct, remaining_s, err, subrun))

            snap["wells"] = well_rows
            snap["all_done"] = bool(boxes) and all_boxes_terminal
            return snap
        except Exception as exc:
            raise UseCaseError("POLL_FAILED", str(exc))
