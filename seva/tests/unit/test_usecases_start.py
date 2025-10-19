from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

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


def _parse_client_dt(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_plan(
    well_snapshots: Dict[str, Dict[str, str]],
    *,
    group_id: str = "group-1",
    experiment: str = _STORAGE["experiment_name"],
    subdir: str = _STORAGE["subdir"],
    client_datetime: str = _STORAGE["client_datetime"],
    make_plot: bool = True,
    tia_gain: Optional[int] = None,
    sampling_interval: Optional[float] = None,
) -> ExperimentPlan:
    meta = PlanMeta(
        experiment=experiment,
        subdir=subdir or None,
        client_dt=ClientDateTime(_parse_client_dt(client_datetime)),
        group_id=GroupId(group_id),
    )
    wells: List[WellPlan] = []
    for wid, snapshot in well_snapshots.items():
        params = CVParams.from_form(snapshot)
        wells.append(
            WellPlan(
                well=WellId(wid),
                mode=ModeName("CV"),
                params=params,
            )
        )
    return ExperimentPlan(
        meta=meta,
        wells=wells,
        make_plot=make_plot,
        tia_gain=tia_gain,
        sampling_interval=sampling_interval,
    )


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


def test_start_experiment_batch_happy_path():
    job_port = _JobMock()
    uc = StartExperimentBatch(job_port=job_port)
    plan = _build_plan({"A1": _cv_snapshot()})

    result = uc(plan)

    assert job_port.calls == 1
    assert result.run_group_id == "group-1"
    assert result.started_wells == ["A1"]
    assert result.per_box_runs == {"A": ["A-run"]}
    assert job_port.last_plan is not None
    job = job_port.last_plan["jobs"][0]
    assert job["box"] == "A"
    assert job["mode"] == "CV"
    assert job["experiment_name"] == _STORAGE["experiment_name"]
    assert job["subdir"] is None
    assert job["client_datetime"] == _STORAGE["client_datetime"]
    assert "run_name" not in job
    assert "folder_name" not in job


def test_start_builds_jobs_for_all_wells():
    job_port = _JobMock()
    uc = StartExperimentBatch(job_port=job_port)
    plan = _build_plan({"A1": _cv_snapshot(), "B2": _cv_snapshot()})

    result = uc(plan)

    assert job_port.calls == 1
    assert result.started_wells == ["A1", "B2"]
    assert set(result.per_box_runs.keys()) == {"A", "B"}


def test_start_yields_one_job_per_well():
    job_port = _JobMock()
    uc = StartExperimentBatch(job_port=job_port)
    plan = _build_plan({"A1": _cv_snapshot(), "B2": _cv_snapshot()})

    uc(plan)

    assert job_port.last_plan is not None
    jobs = job_port.last_plan["jobs"]
    assert len(jobs) == 2

    for job in jobs:
        assert len(job["wells"]) == 1
        assert job["experiment_name"] == _STORAGE["experiment_name"]
        assert job["subdir"] is None
        assert job["client_datetime"] == _STORAGE["client_datetime"]


def test_plan_meta_validation_blocks_bad_input():
    with pytest.raises(ValueError):
        _build_plan({"A1": _cv_snapshot()}, experiment="")
