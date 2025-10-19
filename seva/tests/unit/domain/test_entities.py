from __future__ import annotations

from datetime import datetime, timezone

import pytest

from seva.domain.entities import (
    BoxId,
    BoxSnapshot,
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    GroupSnapshot,
    ModeName,
    ModeParams,
    PlanMeta,
    ProgressPct,
    RunId,
    RunStatus,
    Seconds,
    WellId,
    WellPlan,
)


def test_progress_pct_accepts_number_within_range() -> None:
    progress = ProgressPct(42)
    assert float(progress) == 42.0
    assert str(progress) == "42.00%"


def test_progress_pct_outside_range_raises() -> None:
    with pytest.raises(ValueError):
        ProgressPct(120)


def test_client_datetime_requires_timezone() -> None:
    with pytest.raises(ValueError):
        ClientDateTime(datetime(2025, 10, 18, 12, 0))


def test_experiment_plan_construction_smoke() -> None:
    client_dt = ClientDateTime(datetime(2025, 10, 18, 15, 0, tzinfo=timezone.utc))
    meta = PlanMeta(
        experiment="Battery Screening",
        subdir="plate_01",
        client_dt=client_dt,
        group_id=GroupId("Battery_Screening__20251018T150000Z__AAAA"),
    )
    plan = ExperimentPlan(
        meta=meta,
        wells=[
            WellPlan(
                well=WellId("A1"),
                mode=ModeName("CV"),
                params=ModeParams(flags={"export": True}),
            )
        ],
    )

    assert plan.meta.experiment == "Battery Screening"
    assert str(plan.wells[0].well) == "A1"
    assert plan.wells[0].params.flags["export"] is True


def test_group_snapshot_requires_typed_keys() -> None:
    run_status = RunStatus(
        run_id=RunId("run-1"),
        phase="running",
        progress=ProgressPct(25),
        remaining_s=Seconds(30),
    )
    box_id = BoxId("box-1")
    snapshot = GroupSnapshot(
        group=GroupId("Group__20251018T150000Z__ABCD"),
        runs={WellId("A1"): run_status},
        boxes={box_id: BoxSnapshot(box=box_id, progress=ProgressPct(50))},
        all_done=False,
    )

    assert snapshot.boxes[box_id].progress.value == 50.0


def test_group_snapshot_invalid_key_type_raises() -> None:
    run_status = RunStatus(run_id=RunId("run-1"), phase="queued")
    box_id = BoxId("box-1")

    with pytest.raises(TypeError):
        GroupSnapshot(
            group=GroupId("Group__20251018T150000Z__EFGH"),
            runs={"A1": run_status},  # type: ignore[arg-type]
            boxes={box_id: BoxSnapshot(box=box_id)},
            all_done=False,
        )
