import pytest

from seva.domain.entities import BoxId, GroupId, GroupSnapshot, ProgressPct, Seconds, WellId
from seva.domain.snapshot_normalizer import normalize_status


def test_normalize_status_builds_group_snapshot_with_aggregations():
    raw = {
        "group": "grp-1",
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "running",
                        "progress_pct": 40,
                        "remaining_s": 120,
                    },
                    {
                        "run_id": "run-2",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    },
                ]
            },
            "B": {"runs": []},
        },
        "wells": [
            ("A1", "Running", 0, "", "run-1"),
            ("A2", "Done", 0, "", "run-2"),
        ],
    }

    snapshot = normalize_status(raw)

    assert snapshot.group.value == "grp-1"
    assert snapshot.all_done is False

    box_a = snapshot.boxes[BoxId("A")]
    assert isinstance(box_a.progress, ProgressPct)
    assert box_a.progress.value == pytest.approx(70.0)
    assert isinstance(box_a.remaining_s, Seconds)
    assert int(box_a.remaining_s.value) == 120

    box_b = snapshot.boxes[BoxId("B")]
    assert box_b.progress is None
    assert box_b.remaining_s is None

    run_a1 = snapshot.runs[WellId("A1")]
    assert run_a1.phase == "running"
    assert isinstance(run_a1.progress, ProgressPct)
    assert run_a1.progress.value == pytest.approx(40.0)
    assert isinstance(run_a1.remaining_s, Seconds)
    assert int(run_a1.remaining_s.value) == 120
    assert run_a1.error is None

    run_a2 = snapshot.runs[WellId("A2")]
    assert run_a2.phase == "done"
    assert run_a2.progress.value == pytest.approx(100.0)
    assert isinstance(run_a2.remaining_s, Seconds)
    assert int(run_a2.remaining_s.value) == 0


def test_normalize_status_handles_missing_fields_and_strings():
    raw = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "r-1",
                        "status": None,
                        "progress_pct": "67.5",
                        "remaining_s": "15.2",
                    }
                ]
            },
            "": {"runs": [{"run_id": None}]},
        },
        "wells": [
            ("A1", "Queued", "67.5", "", "r-1"),
            ("A2", "Done", None, "", None),
        ],
        "all_done": "",
    }

    snapshot = normalize_status(raw)

    # Fallback group id should be synthesized.
    assert snapshot.group.value == "unknown-group"
    assert snapshot.all_done is False

    box_a = snapshot.boxes[BoxId("A")]
    assert box_a.progress.value == pytest.approx(67.5)
    assert int(box_a.remaining_s.value) == 15

    run = snapshot.runs[WellId("A1")]
    assert run.phase == "queued"
    assert run.progress.value == pytest.approx(67.5)
    assert int(run.remaining_s.value) == 15
    assert run.error is None

    # Wells without a valid run id are skipped.
    assert WellId("A2") not in snapshot.runs


def test_normalize_status_passthrough_group_snapshot():
    snapshot = GroupSnapshot(
        group=GroupId("grp-1"),
        runs={},
        boxes={},
        all_done=False,
    )

    result = normalize_status(snapshot)

    assert result is snapshot
