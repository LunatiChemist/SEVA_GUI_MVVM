from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    ModeName,
    PlanMeta,
    WellId,
    WellPlan,
)
from seva.domain.params import CVParams
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


def _build_plan(
    experiment: str,
    subdir: Optional[str],
    client_dt: datetime,
) -> ExperimentPlan:
    meta = PlanMeta(
        experiment=experiment,
        subdir=subdir,
        client_dt=ClientDateTime(client_dt),
        group_id=GroupId("group-id"),
    )
    params = CVParams.from_form(_cv_snapshot())
    wells = [
        WellPlan(
            well=WellId("A1"),
            mode=ModeName("CV"),
            params=params,
        )
    ]
    return ExperimentPlan(meta=meta, wells=wells)


def test_plan_jobs_include_storage_metadata():
    job_spy = _JobSpy()
    uc = StartExperimentBatch(job_port=job_spy)
    plan = _build_plan(
        experiment="Experiment Alpha",
        subdir="Batch 001",
        client_dt=datetime(2024, 3, 5, 10, 15, 30, tzinfo=timezone.utc),
    )

    result = uc(plan)

    assert result.run_group_id == "group-id"
    assert job_spy.plan is not None
    job_payload = job_spy.plan["jobs"][0]
    assert job_payload["experiment_name"] == "Experiment Alpha"
    assert job_payload["subdir"] == "Batch 001"
    assert job_payload["client_datetime"] == "2024-03-05T10:15:30Z"


def test_plan_with_optional_subdir_none_serializes_to_none():
    job_spy = _JobSpy()
    uc = StartExperimentBatch(job_port=job_spy)
    plan = _build_plan(
        experiment="Experiment Alpha",
        subdir=None,
        client_dt=datetime(2024, 3, 5, 10, 15, 30, tzinfo=timezone.utc),
    )

    uc(plan)

    assert job_spy.plan is not None
    job_payload = job_spy.plan["jobs"][0]
    assert job_payload["subdir"] is None
