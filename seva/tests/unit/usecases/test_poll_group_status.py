import pytest

from seva.domain.entities import BoxId, GroupId, GroupSnapshot, ProgressPct, Seconds, WellId
from seva.domain.ports import UseCaseError
from seva.usecases.poll_group_status import PollGroupStatus


class _JobPortStub:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.calls = []

    def poll_group(self, run_group_id):
        self.calls.append(run_group_id)
        return self._snapshot


class _FailingJobPort:
    def poll_group(self, run_group_id):
        raise RuntimeError("boom")


def test_poll_group_status_returns_group_snapshot():
    raw_snapshot = {
        "boxes": {
            "A": {
                "runs": [
                    {
                        "run_id": "run-1",
                        "status": "done",
                        "progress_pct": 100,
                        "remaining_s": 0,
                    }
                ]
            }
        },
        "wells": [
            ("A1", "Done", 0, "", "run-1"),
        ],
        "all_done": True,
    }

    uc = PollGroupStatus(job_port=_JobPortStub(raw_snapshot))
    result = uc("grp-42")

    assert isinstance(result, GroupSnapshot)
    assert result.group.value == "grp-42"
    assert result.all_done is True
    assert BoxId("A") in result.boxes
    box = result.boxes[BoxId("A")]
    assert isinstance(box.progress, ProgressPct)
    assert box.progress.value == pytest.approx(100.0)
    assert isinstance(box.remaining_s, Seconds)
    assert int(box.remaining_s.value) == 0

    run = result.runs[WellId("A1")]
    assert run.phase == "done"
    assert run.progress.value == pytest.approx(100.0)
    assert int(run.remaining_s.value) == 0


def test_poll_group_status_wraps_adapter_errors():
    uc = PollGroupStatus(job_port=_FailingJobPort())

    with pytest.raises(UseCaseError) as exc_info:
        uc("grp-error")

    assert exc_info.value.code == "POLL_FAILED"


def test_poll_group_status_accepts_domain_snapshot():
    snapshot = GroupSnapshot(
        group=GroupId("grp-123"),
        runs={},
        boxes={},
        all_done=False,
    )
    uc = PollGroupStatus(job_port=_JobPortStub(snapshot))

    result = uc("grp-123")

    assert result is snapshot


def test_poll_group_status_realigns_group_identifier():
    snapshot = GroupSnapshot(
        group=GroupId("other-group"),
        runs={},
        boxes={},
        all_done=False,
    )
    uc = PollGroupStatus(job_port=_JobPortStub(snapshot))

    result = uc("grp-expected")

    assert result.group.value == "grp-expected"
    assert result is not snapshot
