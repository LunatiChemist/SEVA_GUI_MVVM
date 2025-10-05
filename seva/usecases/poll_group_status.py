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
        try:
            snap = self.job_port.poll_group(run_group_id)
            boxes = snap.get("boxes", {})
            now = datetime.now(timezone.utc)

            # Compute per-run progress and box aggregates
            for box_id, meta in boxes.items():
                runs = meta.get("runs") or []
                run_progresses = []

                for r in runs:
                    run_id = r.get("run_id")
                    status = str(r.get("status") or "queued").lower()
                    started_at = _parse_iso(r.get("started_at"))

                    progress = 0
                    if status == "done":
                        progress = 100
                    elif status == "running" and started_at:
                        planned = get_planned_duration(
                            run_group_id, run_id
                        )  # per-run planned duration
                        if planned and planned > 0:
                            elapsed = (now - started_at).total_seconds()
                            pct = int(
                                round(100 * max(0.0, min(1.0, elapsed / planned)))
                            )
                            # cap at 99% until API says 'done'
                            progress = min(pct, 99)
                        else:
                            progress = 0
                    else:
                        progress = 0

                    r["progress"] = progress
                    run_progresses.append(progress)

                # Box-level progress = mean of run progresses (or 0 if none)
                box_prog = (
                    int(round(sum(run_progresses) / len(run_progresses)))
                    if run_progresses
                    else 0
                )
                meta["progress"] = box_prog

                # If all runs are 'done', override progress to 100 for box
                statuses = {str(r.get("status") or "").lower() for r in runs}
                if statuses and statuses.issubset({"done"}):
                    meta["progress"] = 100
                    if meta.get("phase") != "Failed":
                        meta["phase"] = "Done"
                elif "running" in statuses:
                    meta["phase"] = "Running"
                elif "failed" in statuses and "running" not in statuses:
                    meta["phase"] = "Failed"
                elif "queued" in statuses and not statuses.intersection(
                    {"running", "failed"}
                ):
                    meta["phase"] = "Queued"
                else:
                    meta["phase"] = meta.get("phase") or "Mixed"

            # Propagate per-well progress: take box progress as coarse proxy
            well_rows = []
            for row in snap.get("wells", []):
                # row format: (well_id, state, progress, error, subrun)
                wid, state, _, err, subrun = row
                box = wid[0] if wid else ""
                box_prog = boxes.get(box, {}).get("progress", 0)
                well_rows.append((wid, state, box_prog, err, subrun))

            snap["wells"] = well_rows
            return snap
        except Exception as e:
            raise UseCaseError("POLL_FAILED", str(e))
