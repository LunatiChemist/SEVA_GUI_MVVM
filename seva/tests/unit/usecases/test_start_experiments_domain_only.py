from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

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
from seva.domain.ports import RunGroupId
from seva.usecases.start_experiment_batch import StartBatchResult, StartExperimentBatch


def _build_plan(well_ids: List[str]) -> ExperimentPlan:
    meta = PlanMeta(
        experiment="Experiment Alpha",
        subdir=None,
        client_dt=ClientDateTime(datetime(2025, 3, 4, 5, 6, tzinfo=timezone.utc)),
        group_id=GroupId("grp-001"),
    )
    wells: List[WellPlan] = []
    snapshot = {
        "run_cv": "1",
        "cv.start_v": "0",
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.5",
        "cv.final_v": "0",
        "cv.scan_rate_v_s": "0.1",
        "cv.cycles": "1",
    }
    params = CVParams.from_form(snapshot)
    for wid in well_ids:
        wells.append(
            WellPlan(
                well=WellId(wid),
                mode=ModeName("CV"),
                params=params,
            )
        )
    return ExperimentPlan(meta=meta, wells=wells, make_plot=False)


class _JobPortStub:
    def __init__(self) -> None:
        self.calls = 0
        self.received_plan: Optional[ExperimentPlan] = None

    def start_batch(self, plan: ExperimentPlan) -> tuple[RunGroupId, Dict[str, List[str]]]:
        self.calls += 1
        self.received_plan = plan
        runs: Dict[str, List[str]] = {}
        for well_plan in plan.wells:
            well_id = str(well_plan.well)
            box = well_id[0]
            runs.setdefault(box, []).append(f"{box}-run")
        return str(plan.meta.group_id), runs


def test_start_experiment_batch_uses_experiment_plan_only() -> None:
    job_port = _JobPortStub()
    usecase = StartExperimentBatch(job_port=job_port)
    plan = _build_plan(["A1", "B2"])

    result = usecase(plan)

    assert isinstance(result, StartBatchResult)
    assert job_port.calls == 1
    assert job_port.received_plan is plan
    assert result.started_wells == ["A1", "B2"]
    assert result.per_box_runs == {"A": ["A-run"], "B": ["B-run"]}
    assert result.run_group_id == "grp-001"


def test_start_experiment_batch_rejects_non_domain_input() -> None:
    job_port = _JobPortStub()
    usecase = StartExperimentBatch(job_port=job_port)

    with pytest.raises(TypeError):
        usecase({"selection": ["A1"]})  # type: ignore[arg-type]
