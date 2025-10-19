from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from seva.domain.entities import (
    GroupId,
    GroupSnapshot,
    ProgressPct,
    RunId,
    RunStatus,
    WellId,
)
from seva.usecases.run_flow_coordinator import FlowHooks, RunFlowCoordinator


def _make_settings(**overrides) -> SimpleNamespace:
    defaults = {
        "poll_interval_ms": 1000,
        "poll_backoff_max_ms": 5000,
        "auto_download_on_complete": True,
        "results_dir": "results",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_plan(results_dir: str = "results") -> dict:
    return {
        "group_id": "grp-test",
        "storage": {
            "experiment_name": "TestExp",
            "subdir": "batch",
            "client_datetime": "2024-01-01T00-00-00",
            "results_dir": results_dir,
        },
    }


def _make_snapshot(progress: float, *, phase: str = "running", all_done: bool = False) -> GroupSnapshot:
    status_kwargs = {}
    if progress is not None:
        status_kwargs["progress"] = ProgressPct(progress)
    status = RunStatus(run_id=RunId("run-1"), phase=phase, **status_kwargs)
    return GroupSnapshot(
        group=GroupId("grp-test"),
        runs={WellId("A1"): status},
        boxes={},
        all_done=all_done,
    )


class _DummyStartResult:
    def __init__(self, group_id: str = "grp-test") -> None:
        self.run_group_id = group_id


def _make_coordinator(
    *,
    settings: SimpleNamespace,
    uc_poll,
    uc_download,
    hooks: FlowHooks | None = None,
) -> RunFlowCoordinator:
    return RunFlowCoordinator(
        job_port=object(),
        device_port=object(),
        storage_port=object(),
        uc_validate_start=lambda plan: [],
        uc_start=lambda plan: _DummyStartResult(),
        uc_poll=uc_poll,
        uc_download=uc_download,
        settings=settings,
        hooks=hooks,
    )


def test_backoff_increases_without_progress_and_resets_on_change() -> None:
    snapshots = [
        _make_snapshot(10.0),
        _make_snapshot(10.0),
        _make_snapshot(10.0),
        _make_snapshot(20.0),
    ]

    def uc_poll(_: str):
        if not snapshots:
            pytest.fail("uc_poll called more times than expected")
        return snapshots.pop(0)

    coordinator = _make_coordinator(
        settings=_make_settings(),
        uc_poll=uc_poll,
        uc_download=lambda *args, **kwargs: "unused",
    )
    ctx = coordinator.start(_make_plan())

    tick1 = coordinator.poll_once(ctx)
    assert tick1.event == "tick"
    assert tick1.next_delay_ms == 1000

    tick2 = coordinator.poll_once(ctx)
    assert tick2.event == "tick"
    assert tick2.next_delay_ms == 1500

    tick3 = coordinator.poll_once(ctx)
    assert tick3.event == "tick"
    assert tick3.next_delay_ms == 2250

    tick4 = coordinator.poll_once(ctx)
    assert tick4.event == "tick"
    assert tick4.next_delay_ms == 1000


def test_completed_triggers_auto_download_once(tmp_path: Path) -> None:
    extracted_root = tmp_path / "downloads" / "batch"
    extracted_root.mkdir(parents=True, exist_ok=True)
    download_calls: list[tuple[str, str, dict]] = []
    hook_paths: list[Path] = []

    def uc_download(group_id: str, target_dir: str, storage_meta, **kwargs) -> str:
        download_calls.append((group_id, target_dir, dict(storage_meta)))
        return str(extracted_root)

    hooks = FlowHooks(on_completed=lambda path: hook_paths.append(path))
    plan = _make_plan(str(tmp_path / "results"))
    snapshots = [
        _make_snapshot(10.0),
        _make_snapshot(100.0, phase="done", all_done=True),
    ]

    def uc_poll(_: str):
        if not snapshots:
            pytest.fail("uc_poll called more times than expected")
        return snapshots.pop(0)

    settings = _make_settings(results_dir=str(tmp_path / "results"))
    coordinator = _make_coordinator(
        settings=settings,
        uc_poll=uc_poll,
        uc_download=uc_download,
        hooks=hooks,
    )
    ctx = coordinator.start(plan)
    coordinator.poll_once(ctx)  # warm-up tick
    completed_tick = coordinator.poll_once(ctx)

    assert completed_tick.event == "completed"
    assert completed_tick.next_delay_ms is None
    assert completed_tick.snapshot is not None

    first_path = coordinator.on_completed(ctx, completed_tick.snapshot)
    second_path = coordinator.on_completed(ctx, completed_tick.snapshot)

    assert len(download_calls) == 1
    assert len(hook_paths) == 1
    assert hook_paths[0] == first_path == second_path
    assert download_calls[0][0] == "grp-test"
    assert Path(download_calls[0][1]).resolve() == Path(settings.results_dir).resolve()


def test_poll_error_returns_error_tick_without_delay() -> None:
    errors: list[str] = []

    def uc_poll(_: str) -> None:
        raise RuntimeError("boom")

    hooks = FlowHooks(on_error=lambda message: errors.append(message))
    coordinator = _make_coordinator(
        settings=_make_settings(),
        uc_poll=uc_poll,
        uc_download=lambda *args, **kwargs: "unused",
        hooks=hooks,
    )
    ctx = coordinator.start(_make_plan())
    tick = coordinator.poll_once(ctx)

    assert tick.event == "error"
    assert tick.next_delay_ms is None
    assert tick.error_msg == "boom"
    assert errors == ["boom"]
