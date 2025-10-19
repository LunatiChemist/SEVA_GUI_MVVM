from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from seva.app.main import App
from seva.domain.entities import ClientDateTime, GroupId, PlanMeta
from seva.usecases.run_flow_coordinator import FlowHooks, FlowTick, GroupContext
from seva.usecases.start_experiment_batch import (
    StartBatchResult,
    WellValidationResult,
)


class WinStub:
    def __init__(self) -> None:
        self.after_calls: List[tuple[int, object]] = []
        self.after_cancelled: List[object] = []
        self.toasts: List[str] = []
        self.group_ids: List[str] = []

    def after(self, delay: int, callback) -> str:
        token = f"after-{len(self.after_calls)+1}"
        self.after_calls.append((delay, callback))
        return token

    def after_cancel(self, token: object) -> None:
        self.after_cancelled.append(token)

    def show_toast(self, message: str) -> None:
        self.toasts.append(message)

    def set_run_group_id(self, group_id: str) -> None:
        self.group_ids.append(group_id)


class PlateStub:
    def __init__(self, wells: Iterable[str]) -> None:
        self._wells = list(wells)

    def configured(self) -> List[str]:
        return list(self._wells)

    def get_selection(self) -> List[str]:
        return list(self._wells)


class ExperimentStub:
    def __init__(self) -> None:
        self.selection: List[str] = []

    def set_selection(self, selection: Iterable[str]) -> None:
        self.selection = list(selection)


class SettingsStub:
    def __init__(self) -> None:
        self.use_streaming = False
        self.poll_interval_ms = 750
        self.results_dir = "results"


class ProgressStub:
    def __init__(self) -> None:
        self.snapshots: List[object] = []
        self.last_snapshot = None

    def apply_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)
        self.last_snapshot = snapshot


class WellGridStub:
    def __init__(self) -> None:
        self.configured: List[Sequence[str]] = []

    def add_configured_wells(self, wells: Sequence[str]) -> None:
        self.configured.append(list(wells))


class LogStub:
    def __init__(self) -> None:
        self.infos: List[tuple] = []
        self.debugs: List[tuple] = []
        self.errors: List[tuple] = []

    def info(self, *args, **kwargs) -> None:
        self.infos.append((args, kwargs))

    def debug(self, *args, **kwargs) -> None:
        self.debugs.append((args, kwargs))

    def error(self, *args, **kwargs) -> None:
        self.errors.append((args, kwargs))


def _make_context(group_id: str) -> GroupContext:
    meta = PlanMeta(
        experiment="Experiment",
        subdir=None,
        client_dt=ClientDateTime(datetime.now(timezone.utc)),
        group_id=GroupId(group_id),
    )
    return GroupContext(group=GroupId(group_id), meta=meta, run_index={})


class CoordinatorStub:
    def __init__(
        self,
        *,
        group_id: str,
        validations: Sequence[WellValidationResult],
        start_result: StartBatchResult,
        poll_result: FlowTick,
    ) -> None:
        self.validations = list(validations)
        self.start_result = start_result
        self.poll_result = poll_result
        self.ctx = _make_context(group_id)
        self.start_called = False
        self.stop_called = False
        self.hooks = None

    def validate(self, plan) -> Sequence[WellValidationResult]:
        self.validated_plan = plan
        return list(self.validations)

    def start(self, plan) -> GroupContext:
        self.start_called = True
        return self.ctx

    def last_start_result(self) -> StartBatchResult:
        return self.start_result

    def poll_once(self, ctx: GroupContext) -> FlowTick:
        if self.hooks:
            if self.poll_result.snapshot:
                self.hooks.on_snapshot(self.poll_result.snapshot)
            if self.poll_result.event == "error":
                self.hooks.on_error(self.poll_result.error_msg or "")
        return self.poll_result

    def stop_polling(self) -> None:
        self.stop_called = True


def _make_validation(ok: bool = True) -> WellValidationResult:
    return WellValidationResult(
        well_id="A1",
        box_id="A",
        mode="CV",
        ok=ok,
        errors=[] if ok else [{"msg": "invalid"}],
        warnings=[],
    )


def _make_plan(group_id: str) -> dict:
    return {
        "group_id": group_id,
        "storage": {
            "experiment_name": "Experiment",
            "subdir": "batch",
            "client_datetime": "2024-01-01T00-00-00",
            "results_dir": "results",
        },
    }


def _make_app(
    *,
    validations: Sequence[WellValidationResult],
    start_result: StartBatchResult,
    poll_result: FlowTick,
) -> tuple[App, CoordinatorStub, WinStub]:
    app = App.__new__(App)
    win = WinStub()
    app.win = win
    app._log = LogStub()
    app.plate_vm = PlateStub(["A1"])
    app.experiment_vm = ExperimentStub()
    app.settings_vm = SettingsStub()
    app.progress_vm = ProgressStub()
    app.wellgrid = WellGridStub()
    app._group_storage_meta = {}
    app._current_group_id = None
    app._flow_ctx = None
    app._poll_after_id = None
    app._storage_root = "."
    app._storage = None
    group_id = start_result.run_group_id or "grp-test"
    app._build_plan_from_vm = lambda selection: _make_plan(group_id)
    app._ensure_adapter = lambda: True
    app._ensure_coordinator = lambda: True
    app._flow_hooks = FlowHooks(
        on_started=app._on_flow_started,
        on_snapshot=app._on_flow_snapshot,
        on_completed=app._on_flow_completed,
        on_error=app._on_flow_error,
        on_validation_errors=app._handle_start_validations,
    )

    coordinator = CoordinatorStub(
        group_id=group_id,
        validations=validations,
        start_result=start_result,
        poll_result=poll_result,
    )
    coordinator.hooks = app._flow_hooks
    app._coordinator = coordinator
    return app, coordinator, win


def test_submit_with_validation_errors_aborts_without_timer() -> None:
    validations = [_make_validation(ok=False)]
    start_result = StartBatchResult(
        run_group_id=None,
        per_box_runs={},
        started_wells=[],
        validations=validations,
    )
    poll_result = FlowTick(event="tick", next_delay_ms=250)
    app, coordinator, win = _make_app(
        validations=validations,
        start_result=start_result,
        poll_result=poll_result,
    )

    app._on_submit()

    assert coordinator.start_called is False
    assert win.after_calls == []


def test_submit_success_schedules_next_poll_on_tick_event() -> None:
    validations = [_make_validation(ok=True)]
    start_result = StartBatchResult(
        run_group_id="grp-123",
        per_box_runs={"A": ["run-1"]},
        started_wells=["A1"],
        validations=list(validations),
    )
    poll_result = FlowTick(event="tick", next_delay_ms=300)
    app, coordinator, win = _make_app(
        validations=validations,
        start_result=start_result,
        poll_result=poll_result,
    )

    app._on_submit()

    assert coordinator.start_called is True
    assert win.after_calls
    delay, _callback = win.after_calls[0]
    assert delay == 300


def test_poll_completed_stops_without_reschedule() -> None:
    validations = [_make_validation(ok=True)]
    start_result = StartBatchResult(
        run_group_id="grp-456",
        per_box_runs={"A": ["run-1"]},
        started_wells=["A1"],
        validations=list(validations),
    )
    poll_result = FlowTick(event="completed")
    app, coordinator, win = _make_app(
        validations=validations,
        start_result=start_result,
        poll_result=poll_result,
    )

    app._flow_ctx = coordinator.ctx
    app._on_poll_tick()

    assert win.after_calls == []
    assert coordinator.stop_called is True
    assert "All runs completed." in win.toasts


def test_poll_error_stops_and_clears_context() -> None:
    validations = [_make_validation(ok=True)]
    start_result = StartBatchResult(
        run_group_id="grp-789",
        per_box_runs={"A": ["run-1"]},
        started_wells=["A1"],
        validations=list(validations),
    )
    poll_result = FlowTick(event="error", error_msg="Polling failed.")
    app, coordinator, win = _make_app(
        validations=validations,
        start_result=start_result,
        poll_result=poll_result,
    )

    app._flow_ctx = coordinator.ctx
    app._on_poll_tick()

    assert win.after_calls == []
    assert coordinator.stop_called is True
    assert app._flow_ctx is None
    assert "Polling failed." in win.toasts
