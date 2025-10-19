from __future__ import annotations

from typing import Any, Dict, Iterable, List
from seva.usecases.start_experiment_batch import StartExperimentBatch


class _JobSpy:
    def __init__(self) -> None:
        self.calls = 0
        self.payloads: List[Dict[str, Any]] = []

    def start_batch(self, plan: Dict[str, Any]):
        self.calls += 1
        self.payloads.append(plan)
        per_box: Dict[str, List[str]] = {}
        for job in plan.get("jobs", []):
            box = job.get("box")
            per_box.setdefault(box, []).append(f"{box}-run")
        return ("grp-123", per_box)


class _DeviceStub:
    def __init__(self) -> None:
        self.called = False

    def validate_mode(self, box_id: str, mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.called = True
        raise AssertionError("StartExperimentBatch must not call device validation")


def _plan(selection: Iterable[str]) -> Dict[str, Any]:
    return {
        "selection": list(selection),
        "well_params_map": {
            wid: {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.1",
                "cv.vertex2_v": "-0.1",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "1",
            }
            for wid in selection
        },
        "storage": {
            "experiment_name": "All Or Nothing",
            "subdir": "Batch",
            "client_datetime": "2024-05-06T07:08:09Z",
        },
    }


def test_start_does_not_attempt_device_validation():
    device = _DeviceStub()
    job = _JobSpy()
    uc = StartExperimentBatch(job_port=job, device_port=device)

    result = uc(_plan(["A1"]))

    assert job.calls == 1
    assert not device.called
    assert result.started_wells == ["A1"]
    assert result.validations == []


def test_successful_start_returns_group_id_and_calls_job_port_once():
    device = _DeviceStub()
    job = _JobSpy()
    uc = StartExperimentBatch(job_port=job, device_port=device)

    result = uc(_plan(["A1", "B2"]))

    assert job.calls == 1
    assert not device.called
    assert result.run_group_id == "grp-123"
    assert result.started_wells == ["A1", "B2"]
    assert result.per_box_runs == {"A": ["A-run"], "B": ["B-run"]}
    assert result.validations == []
