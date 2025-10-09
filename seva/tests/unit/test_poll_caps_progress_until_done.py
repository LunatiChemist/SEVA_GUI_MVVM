from datetime import datetime, timedelta, timezone

import pytest

from seva.usecases.poll_group_status import PollGroupStatus


class _DummyJobPort:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def poll_group(self, run_group_id):
        return self._snapshot


@pytest.mark.parametrize("elapsed_seconds", [200])
def test_poll_caps_progress_until_done(monkeypatch, elapsed_seconds):
    now = datetime.now(timezone.utc)
    running_start = (now - timedelta(seconds=elapsed_seconds)).isoformat()

    snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {"run_id": "run-1", "status": "running", "started_at": running_start},
                    {"run_id": "run-2", "status": "queued", "started_at": None},
                ],
                "phase": "Running",
            },
            "B": {
                "runs": [
                    {"run_id": "run-3", "status": "done", "started_at": running_start},
                    {"run_id": "run-4", "status": "failed", "started_at": None},
                ],
                "phase": "Done",
            },
        },
        "wells": [],
    }

    monkeypatch.setattr(
        "seva.usecases.poll_group_status.get_planned_duration",
        lambda group_id, run_id: 10,
    )

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-1")

    box_a = result["boxes"]["A"]
    progress_running = box_a["runs"][0]["progress"]
    assert 0 <= progress_running <= 99
    assert box_a["runs"][1]["progress"] == 0
    assert box_a["progress"] <= 99
    assert box_a["phase"] == "Running"

    box_b = result["boxes"]["B"]
    assert all(run["progress"] == 100 for run in box_b["runs"])
    assert box_b["progress"] == 100
    assert box_b["phase"] == "Failed"
