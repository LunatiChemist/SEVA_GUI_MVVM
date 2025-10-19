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
    assert result["boxes"]["A"]["progress"] == 71
    assert result["boxes"]["A"]["remaining_s"] == 120

    wells = result["wells"]
    assert wells[0] == ("A1", "Running", 42, 120, "", "run-1")
    assert wells[1] == ("A2", "Done", 100, 0, "", "run-2")
    assert isinstance(wells[0][3], int)
    assert isinstance(wells[1][3], int)
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
    assert wells[0][3] == 0
    assert wells[0][5] == "run-3"
    assert wells[1][3] == 0
    assert wells[1][5] == "run-4"


def test_poll_group_status_sets_box_remaining_to_max_for_active_runs():
    snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "running",
                        "progress_pct": 25,
                        "remaining_s": 120,
                    },
                    {
                        "run_id": "run-2",
                        "status": "queued",
                        "progress_pct": 0,
                        "remaining_s": 180,
                    },
                    {
                        "run_id": "run-3",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                ],
                "phase": "Running",
            }
        },
        "wells": [],
    }

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-3")

    assert result["boxes"]["A"]["remaining_s"] == 180
    assert result["boxes"]["A"]["progress"] == 42


def test_poll_group_status_sets_box_remaining_none_when_no_active_runs():
    snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                    {
                        "run_id": "run-2",
                        "status": "cancelled",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                ],
                "phase": "Done",
            },
            "B": {
                "runs": [],
                "phase": "Idle",
            },
        },
        "wells": [],
    }

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-4")

    assert result["boxes"]["A"]["remaining_s"] is None
    assert result["boxes"]["B"]["remaining_s"] is None
    assert result["boxes"]["A"]["progress"] == 100
    assert result["boxes"]["B"]["progress"] is None


def test_poll_group_status_coerces_string_metrics():
    snapshot = {
        "boxes": {
            "B": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "running",
                        "progress_pct": "10",
                        "remaining_s": "5.4",
                    },
                    {
                        "run_id": "run-2",
                        "status": "failed",
                        "progress_pct": "50",
                        "remaining_s": "0",
                    },
                ],
                "phase": "Running",
            }
        },
        "wells": [
            ("B1", "Running", "9", "", "run-1"),
            ("B2", "Error", 0, "Overvoltage", "run-2"),
        ],
    }

    uc = PollGroupStatus(job_port=_DummyJobPort(snapshot))
    result = uc("group-5")

    wells = result["wells"]
    assert wells[0] == ("B1", "Running", 10, 5, "", "run-1")
    assert wells[1] == ("B2", "Error", 50, 0, "Overvoltage", "run-2")
    assert result["boxes"]["B"]["progress"] == 30
    assert result["boxes"]["B"]["remaining_s"] == 5
