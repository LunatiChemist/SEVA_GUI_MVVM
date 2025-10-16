from seva.usecases.poll_group_status import PollGroupStatus


class _DummyJobPort:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def poll_group(self, run_group_id):
        return self._snapshot


def test_poll_group_status_passes_through_server_metrics():
    snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "running",
                        "progress_pct": 42,
                        "remaining_s": 120,
                    },
                    {
                        "run_id": "run-2",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                ],
                "phase": "Running",
            }
        },
        "wells": [
            ("A1", "Running", 0, "", "run-1"),
            ("A2", "Done", 0, "", "run-2"),
        ],
    }

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-1")

    runs = result["boxes"]["A"]["runs"]
    assert runs[0]["progress_pct"] == 42
    assert runs[0]["remaining_s"] == 120
    assert runs[1]["remaining_s"] == 0
    assert "progress" not in runs[0]
    assert "progress" not in runs[1]

    wells = result["wells"]
    assert wells[0] == ("A1", "Running", 42, "", "run-1", 120)
    assert wells[1] == ("A2", "Done", 100, "", "run-2", 0)
    assert result["all_done"] is False


def test_poll_group_status_sets_all_done_for_terminal_boxes():
    snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-3",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                    {
                        "run_id": "run-4",
                        "status": "failed",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                ],
                "phase": "Running",
            }
        },
        "wells": [
            ("A3", "Done", 0, "", "run-3"),
            ("A4", "Error", 0, "", "run-4"),
        ],
    }

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-2")

    assert result["all_done"] is True
    assert result["boxes"]["A"]["phase"] == snapshot["boxes"]["A"]["phase"]
    wells = result["wells"]
    assert wells[0][-1] == 0
    assert wells[1][-1] == 0
