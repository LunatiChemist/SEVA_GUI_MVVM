from __future__ import annotations

from typing import Any, Dict, List, Optional

from seva.domain.ports import UseCaseError
from seva.usecases.start_experiment_batch import StartExperimentBatch


def _cv_snapshot() -> Dict[str, str]:
    return {
        "run_cv": "1",
        "cv.start_v": "0",
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.5",
        "cv.final_v": "0",
        "cv.scan_rate_v_s": "0.2",
        "cv.cycles": "2",
    }


class _JobSpy:
    def __init__(self) -> None:
        self.plan: Optional[Dict[str, Any]] = None

    def start_batch(self, plan: Dict[str, Any]):
        self.plan = plan
        per_box: Dict[str, List[str]] = {}
        for job in plan.get("jobs", []):
            box = job.get("box")
            per_box.setdefault(box, []).append(f"{box}-run")
        return ("group-id", per_box)


class _DeviceStub:
    def validate_mode(self, box_id: str, mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "errors": [], "warnings": []}


def test_plan_jobs_include_storage_metadata():
    job_spy = _JobSpy()
    uc = StartExperimentBatch(job_port=job_spy, device_port=_DeviceStub())
    plan: Dict[str, Any] = {
        "selection": ["A1"],
        "well_params_map": {"A1": _cv_snapshot()},
        "storage": {
            "experiment_name": "Experiment Alpha",
            "subdir": "Batch 001",
            "client_datetime": "2024-03-05_10-15-30",
        },
    }

    result = uc(plan)

    assert result.run_group_id == "group-id"
    assert job_spy.plan is not None
    job_payload = job_spy.plan["jobs"][0]
    assert job_payload["experiment_name"] == "Experiment Alpha"
    assert job_payload["subdir"] == "Batch 001"
    assert job_payload["client_datetime"] == "2024-03-05_10-15-30"


def test_plan_without_metadata_still_starts():
    job_spy = _JobSpy()
    uc = StartExperimentBatch(job_port=job_spy, device_port=_DeviceStub())
    plan: Dict[str, Any] = {
        "selection": ["A1"],
        "well_params_map": {"A1": _cv_snapshot()},
    }

    try:
        uc(plan)
    except Exception as exc:
        assert isinstance(exc, UseCaseError)
    else:
        raise AssertionError("Expected UseCaseError for missing metadata")
