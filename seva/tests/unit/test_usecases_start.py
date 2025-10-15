from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

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
        self.response_queue: List[Dict[str, Any]] = list(response_queue or [])
        self.calls: List[Dict[str, Any]] = []

    def validate_mode(self, box_id: str, mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"box": box_id, "mode": mode, "params": params})
        if self.response_queue:
            return self.response_queue.pop(0)
        return {"ok": True, "errors": [], "warnings": []}


def test_start_experiment_batch_happy_path():
    job_port = _JobMock()
    device_port = _DeviceMock()
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1"],
        "well_params_map": {"A1": _cv_snapshot()},
        "group_id": "group-1",
    }

    result = uc(plan)

    assert result.run_group_id == "group-1"
    assert result.started_wells == ["A1"]
    assert result.per_box_runs == {"A": ["A-run"]}
    assert all(entry.ok for entry in result.validations)
    assert job_port.last_plan is not None
    job = job_port.last_plan["jobs"][0]
    assert job["box"] == "A"
    assert job["mode"] == "CV"


def test_start_skips_invalid_wells_and_starts_remaining():
    invalid_response = {"ok": False, "errors": [{"field": "start", "code": "missing_field"}], "warnings": []}
    valid_response = {"ok": True, "errors": [], "warnings": []}
    job_port = _JobMock()
    device_port = _DeviceMock(response_queue=[invalid_response, valid_response])
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1", "B2"],
        "well_params_map": {"A1": _cv_snapshot(), "B2": _cv_snapshot()},
    }

    result = uc(plan)

    assert job_port.calls == 1
    assert result.run_group_id == "group-1"
    assert result.started_wells == ["B2"]
    assert result.per_box_runs == {"B": ["B-run"]}
    assert len(result.validations) == 2
    assert not result.validations[0].ok
    assert result.validations[1].ok
    assert job_port.last_plan is not None
    jobs = job_port.last_plan["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["wells"] == ["B2"]


def test_start_returns_empty_result_when_all_wells_invalid():
    queue = [
        {"ok": False, "errors": [{"field": "start", "code": "missing_field"}], "warnings": []},
        {"ok": False, "errors": [{"field": "scan_rate", "code": "must_be_positive"}], "warnings": []},
    ]
    job_port = _JobMock()
    device_port = _DeviceMock(response_queue=queue)
    uc = StartExperimentBatch(job_port=job_port, device_port=device_port)
    plan = {
        "selection": ["A1", "A2"],
        "well_params_map": {"A1": _cv_snapshot(), "A2": _cv_snapshot()},
    }

    result = uc(plan)

    assert job_port.calls == 0
    assert result.run_group_id is None
    assert result.per_box_runs == {}
    assert result.started_wells == []
    assert len(result.validations) == 2
    assert all(not entry.ok for entry in result.validations)
