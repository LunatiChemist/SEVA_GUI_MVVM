from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, timezone

from seva.domain.ports import JobPort, UseCaseError, RunGroupId
from seva.usecases.group_registry import get_planned_duration


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None


@dataclass
class PollGroupStatus:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> Dict:
        """
        Enrich raw snapshot from adapter with client-side progress %.
        - Status (queued/running/done/failed) from API is authoritative.
        - Progress % is computed per run_id using started_at + planned_duration_s.
        - 99% cap while API status != 'done'; jump to 100% when 'done'.
        """
        run_info = {}  # run_id -> {"progress": int, "status": str, "error": str}
        try:
            snap = self.job_port.poll_group(run_group_id)
            boxes = snap.get("boxes", {})
            now = datetime.now(timezone.utc)

            # Compute per-run progress and box aggregates
            for box_id, meta in boxes.items():
                runs = meta.get("runs") or []
                run_progresses = []
                statuses = []

                for r in runs:
                    run_id = r.get("run_id")
                    status = str(r.get("status") or "queued").lower()
                    statuses.append(status)
                    started_at = _parse_iso(r.get("started_at"))
                    progress = 0
                    if status == "done":
                        progress = 100
                    elif status == "failed":
                        progress = 100
                    elif status == "running":
                        planned = get_planned_duration(
                            run_group_id, run_id
                        )  # per-run planned duration
                        if planned and planned > 0 and started_at:
                            elapsed = (now - started_at).total_seconds()
                            pct = int(
                                round(100 * max(0.0, min(1.0, elapsed / planned)))
                            )
                            progress = min(pct, 99)
                        else:
                            progress = 0
                    else:
                        progress = 0

                    if status == "running" and progress > 99:
                        progress = 99
                    r["progress"] = progress
                    run_progresses.append(progress)
                    run_info[run_id] = {
                        "progress": progress,
                    }

                if run_progresses:
                    box_prog = int(round(sum(run_progresses) / len(run_progresses)))
                else:
                    box_prog = 0

                statuses_set = set(statuses)
                has_incomplete = any(s in {"queued", "running"} for s in statuses_set)
                all_terminal = statuses and not has_incomplete and statuses_set.issubset(
                    {"done", "failed"}
                )

                if all_terminal:
                    meta["progress"] = 100
                elif has_incomplete:
                    meta["progress"] = min(box_prog, 99)
                else:
                    meta["progress"] = box_prog

                if all_terminal:
                    meta["phase"] = "Failed" if "failed" in statuses_set else "Done"
                elif "running" in statuses_set:
                    meta["phase"] = "Running"
                elif "queued" in statuses_set and "running" not in statuses_set:
                    meta["phase"] = "Queued"
                elif "failed" in statuses_set and "running" not in statuses_set:
                    meta["phase"] = "Failed"
                else:
                    meta["phase"] = meta.get("phase") or "Mixed"

            # Propagate per-well progress: take box progress as coarse proxy
            well_rows = []
            for row in snap.get("wells", []):
                # row format: (well_id, state, progress, error, subrun)
                wid, state, _, err, subrun = row
                info = run_info.get(subrun)  # subrun ist die run_id der Zeile
                if info:
                    p = info["progress"]
                else:
                    p = 0
                well_rows.append((wid, state, p, err, subrun))

            snap["wells"] = well_rows
            snap["all_done"] = bool(boxes) and all(
                (meta.get("phase") in {"Done", "Failed"}) for meta in boxes.values()
            )
            return snap
        except Exception as e:
            raise UseCaseError("POLL_FAILED", str(e))
