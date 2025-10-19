from __future__ import annotations

import pytest
from typing import Any, Dict, Iterable, List, Optional

from seva.domain.ports import UseCaseError
from seva.usecases.start_experiment_batch import StartExperimentBatch


def _cv_snapshot() -> Dict[str, str]:
    return {
        "run_cv": "1",
        "cv.start_v": "0",
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.5",
        "cv.final_v": "0",
        "cv.scan_rate_v_s": "0.1",
        "cv.cycles": "1",
    }

_STORAGE = {
    "experiment_name": "Experiment Alpha",
    "subdir": "",
    "client_datetime": "2024-01-02T03:04:05Z",
}

class _JobMock:
    def __init__(self) -> None:
        self.last_plan: Optional[Dict[str, Any]] = None
        self.calls = 0

    def start_batch(self, plan: Dict[str, Any]):
        self.calls += 1
        self.last_plan = plan
        per_box: Dict[str, List[str]] = {}
        for job in plan.get("jobs", []):
            box = job.get("box")
            per_box.setdefault(box, []).append(f"{box}-run")
        return ("group-1", per_box)


class _DeviceMock:
    def __init__(self, response_queue: Optional[Iterable[Dict[str, Any]]] = None) -> None:
        self.calls: List[Dict[str, Any]] = []

    def validate_mode(self, box_id: str, mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"box": box_id, "mode": mode, "params": params})
        return {"ok": True, "errors": [], "warnings": []}
def test_start_experiment_batch_happy_path():
    job_port = _JobMock()
    device_port = _DeviceMock()
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1"],
        "well_params_map": {"A1": _cv_snapshot()},
        "group_id": "group-1",
        "storage": dict(_STORAGE),
    }

    result = uc(plan)

    assert job_port.calls == 1
    assert result.run_group_id == "group-1"
    assert result.started_wells == ["A1"]
    assert result.per_box_runs == {"A": ["A-run"]}
    assert result.validations == []
    assert device_port.calls == []
    assert job_port.last_plan is not None
    job = job_port.last_plan["jobs"][0]
    assert job["box"] == "A"
    assert job["mode"] == "CV"
    assert job["experiment_name"] == _STORAGE["experiment_name"]
    assert job["subdir"] is None
    assert job["client_datetime"] == _STORAGE["client_datetime"]
    assert "run_name" not in job
    assert "folder_name" not in job


def test_start_builds_jobs_for_all_wells_without_device_validation():
    job_port = _JobMock()
    device_port = _DeviceMock()
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1", "B2"],
        "well_params_map": {"A1": _cv_snapshot(), "B2": _cv_snapshot()},
        "storage": dict(_STORAGE),
    }

    result = uc(plan)

    assert job_port.calls == 1
    assert result.started_wells == ["A1", "B2"]
    assert set(result.per_box_runs.keys()) == {"A", "B"}
    assert result.validations == []
    assert device_port.calls == []


def test_start_yields_one_job_per_well_without_metadata():
    job_port = _JobMock()
    device_port = _DeviceMock()
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1", "B2"],
        "well_params_map": {"A1": _cv_snapshot(), "B2": _cv_snapshot()},
        "storage": dict(_STORAGE),
    }

    uc(plan)

    assert job_port.last_plan is not None
    jobs = job_port.last_plan["jobs"]
    assert len(jobs) == 2

    for job in jobs:
        assert len(job["wells"]) == 1
        assert job["experiment_name"] == _STORAGE["experiment_name"]
        assert job["subdir"] is None
        assert job["client_datetime"] == _STORAGE["client_datetime"]


def test_start_without_metadata_raises_error():
    job_port = _JobMock()
    device_port = _DeviceMock()
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1"],
        "well_params_map": {"A1": _cv_snapshot()},
    }

    with pytest.raises(UseCaseError) as exc:
        uc(plan)
    assert exc.value.code == "METADATA_MISSING"
