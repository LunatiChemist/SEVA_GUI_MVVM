# seva/usecases/poll_group_status.py
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
        # tolerate 'Z' suffix
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None


@dataclass
class PollGroupStatus:
    job_port: JobPort

    def __call__(self, run_group_id: RunGroupId) -> Dict:
        """Fetch raw snapshot from adapter and enrich with client-side progress%."""
        try:
            snap = self.job_port.poll_group(run_group_id)
            boxes = snap.get("boxes", {})
            now = datetime.now(timezone.utc)

            for box_id, meta in boxes.items():
                started_at = _parse_iso(meta.get("started_at"))
                finished_at = _parse_iso(meta.get("finished_at"))
                planned = get_planned_duration(run_group_id, box_id)

                progress = 0
                if finished_at:
                    progress = 100
                elif started_at and planned and planned > 0:
                    elapsed = (now - started_at).total_seconds()
                    pct = int(round(100 * max(0.0, min(1.0, elapsed / planned))))
                    progress = pct
                else:
                    progress = 0

                meta["progress"] = progress  # inject % for UI

            # Optionally propagate box progress to wells entries (index 2)
            well_rows = []
            for row in snap.get("wells", []):
                # row format: (well_id, state, progress, error, subrun)
                wid, state, _, err, subrun = row
                # derive box prefix from well_id[0]
                box = wid[0] if wid else ""
                box_prog = boxes.get(box, {}).get("progress", 0)
                well_rows.append((wid, state, box_prog, err, subrun))

            snap["wells"] = well_rows
            return snap
        except Exception as e:
            raise UseCaseError("POLL_FAILED", str(e))
