from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

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


def _plan(selection: Iterable[str]) -> ExperimentPlan:
    dt = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
    meta = PlanMeta(
        experiment="All Or Nothing",
        subdir="Batch",
        client_dt=ClientDateTime(dt),
        group_id=GroupId("grp-123"),
    )
    wells: List[WellPlan] = []
    for wid in selection:
        params = CVParams.from_form(
            {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.1",
                "cv.vertex2_v": "-0.1",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "1",
            }
        )
        wells.append(
            WellPlan(
                well=WellId(wid),
                mode=ModeName("CV"),
                params=params,
            )
        )
    return ExperimentPlan(meta=meta, wells=wells)


def test_start_calls_job_port_once():
    job = _JobSpy()
    uc = StartExperimentBatch(job_port=job)

    result = uc(_plan(["A1"]))

    assert job.calls == 1
    assert result.started_wells == ["A1"]


def test_successful_start_returns_group_id_and_jobs():
    job = _JobSpy()
    uc = StartExperimentBatch(job_port=job)

    result = uc(_plan(["A1", "B2"]))

    assert job.calls == 1
    assert result.run_group_id == "grp-123"
    assert result.started_wells == ["A1", "B2"]
    assert result.per_box_runs == {"A": ["A-run"], "B": ["B-run"]}
