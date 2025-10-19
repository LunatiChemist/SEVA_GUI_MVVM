from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, sentinel

from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    GroupSnapshot,
    ModeName,
    ModeParams,
    PlanMeta,
    WellId,
    WellPlan,
)
from seva.usecases.run_flow_coordinator import (
    FlowHooks,
    FlowTick,
    GroupContext,
    RunFlowCoordinator,
)


def _build_plan() -> ExperimentPlan:
    meta = PlanMeta(
        experiment="Experiment",
        subdir=None,
        client_dt=ClientDateTime(datetime.now(timezone.utc)),
        group_id=GroupId("plan-001"),
    )
    wells = [
        WellPlan(
            well=WellId("A1"),
            mode=ModeName("CV"),
            params=ModeParams(flags={}),
        )
    ]
    return ExperimentPlan(meta=meta, wells=wells)


def _make_coordinator(
    *,
    hooks: FlowHooks | None = None,
    uc_validate,
    uc_start,
    uc_poll,
) -> RunFlowCoordinator:
    return RunFlowCoordinator(
        job_port=MagicMock(),
        device_port=MagicMock(),
        storage_port=MagicMock(),
        uc_validate_start=uc_validate,
        uc_start=uc_start,
        uc_poll=uc_poll,
        uc_download=MagicMock(),
        settings=SimpleNamespace(poll_interval_ms=750, poll_backoff_max_ms=5000, auto_download_on_complete=False, results_dir="results"),
        hooks=hooks,
    )


def test_validate_delegates_use_case() -> None:
    plan = _build_plan()
    uc_validate = MagicMock(return_value=[sentinel.validation])
    coordinator = _make_coordinator(
        hooks=FlowHooks(),
        uc_validate=uc_validate,
        uc_start=MagicMock(),
        uc_poll=MagicMock(),
    )

    summary = coordinator.validate(plan)

    assert summary == [sentinel.validation]
    uc_validate.assert_called_once_with(plan)


def test_start_returns_context_and_fires_hook() -> None:
    plan = _build_plan()
    hook_started = MagicMock()
    hooks = FlowHooks(on_started=hook_started)
    uc_start = MagicMock(return_value=SimpleNamespace(run_group_id="run-123"))
    coordinator = _make_coordinator(
        hooks=hooks,
        uc_validate=MagicMock(),
        uc_start=uc_start,
        uc_poll=MagicMock(),
    )

    ctx = coordinator.start(plan)

    assert isinstance(ctx, GroupContext)
    assert ctx.group.value == "run-123"
    assert ctx.meta is plan.meta
    assert ctx.run_index == {}
    uc_start.assert_called_once_with(plan)
    hook_started.assert_called_once_with(ctx)


def test_poll_once_returns_tick_and_emits_snapshot_hook() -> None:
    plan = _build_plan()
    snapshot = GroupSnapshot(group=GroupId("run-123"), runs={}, boxes={}, all_done=False)
    hook_snapshot = MagicMock()
    hooks = FlowHooks(on_snapshot=hook_snapshot)
    uc_start = MagicMock(return_value=SimpleNamespace(run_group_id="run-123"))
    uc_poll = MagicMock(return_value=snapshot)
    coordinator = _make_coordinator(
        hooks=hooks,
        uc_validate=MagicMock(),
        uc_start=uc_start,
        uc_poll=uc_poll,
    )
    ctx = coordinator.start(plan)

    tick = coordinator.poll_once(ctx)

    assert isinstance(tick, FlowTick)
    assert tick.event == "tick"
    assert tick.snapshot is snapshot
    assert tick.next_delay_ms == 750
    uc_poll.assert_called_once_with(str(ctx.group))
    hook_snapshot.assert_called_once_with(snapshot)
