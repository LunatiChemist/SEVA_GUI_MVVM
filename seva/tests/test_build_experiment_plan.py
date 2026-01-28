from __future__ import annotations

import pytest

from seva.domain.params import CVParams
from seva.domain.ports import UseCaseError
from seva.usecases.build_experiment_plan import (
    BuildExperimentPlan,
    ExperimentPlanRequest,
    ModeSnapshot,
    WellSnapshot,
)


def _request_with_cv() -> ExperimentPlanRequest:
    return ExperimentPlanRequest(
        experiment_name="Test Experiment",
        subdir="Subdir",
        client_datetime_override="2025-01-01_10-00-00",
        wells=("A1",),
        well_snapshots=(
            WellSnapshot(
                well_id="A1",
                modes=(
                    ModeSnapshot(
                        name="CV",
                        params={"cv.start_v": "0.1", "run_cv": "1"},
                    ),
                ),
            ),
        ),
    )


def test_build_experiment_plan_builds_plan() -> None:
    plan = BuildExperimentPlan()(_request_with_cv())
    assert plan.meta.experiment == "Test Experiment"
    assert plan.meta.subdir == "Subdir"
    assert plan.meta.client_dt.value.tzinfo is not None
    assert len(plan.wells) == 1
    assert str(plan.wells[0].well) == "A1"
    assert [str(mode) for mode in plan.wells[0].modes] == ["CV"]
    params = list(plan.wells[0].params_by_mode.values())
    assert len(params) == 1
    assert isinstance(params[0], CVParams)


def test_build_experiment_plan_requires_experiment_name() -> None:
    request = _request_with_cv()
    request = ExperimentPlanRequest(
        experiment_name="",
        subdir=request.subdir,
        client_datetime_override=request.client_datetime_override,
        wells=request.wells,
        well_snapshots=request.well_snapshots,
    )
    with pytest.raises(UseCaseError) as exc:
        BuildExperimentPlan()(request)
    assert exc.value.code == "MISSING_EXPERIMENT"


def test_build_experiment_plan_requires_params() -> None:
    request = ExperimentPlanRequest(
        experiment_name="Test",
        subdir=None,
        client_datetime_override="",
        wells=("A1",),
        well_snapshots=tuple(),
    )
    with pytest.raises(UseCaseError) as exc:
        BuildExperimentPlan()(request)
    assert exc.value.code == "MISSING_PARAMS"
