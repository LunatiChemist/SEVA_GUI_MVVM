from __future__ import annotations

import logging
from types import SimpleNamespace

from seva.app.main import App
from seva.viewmodels.progress_vm import ProgressVM
from seva.domain.entities import GroupId, GroupSnapshot, RunId, RunStatus, WellId


def _build_progress_snapshot() -> ProgressVM:
    vm = ProgressVM()
    snapshot = GroupSnapshot(
        group=GroupId("grp-42"),
        runs={
            WellId("A1"): RunStatus(run_id=RunId("run-a1"), phase="running"),
            WellId("B1"): RunStatus(run_id=RunId("run-b"), phase="running"),
            WellId("B2"): RunStatus(run_id=RunId("run-b"), phase="running"),
        },
        boxes={},
        all_done=False,
    )
    vm.apply_snapshot(snapshot)
    return vm


def test_on_end_selection_invokes_cancel_runs_with_mapped_payload():
    app = App.__new__(App)

    selection = {"A1", "B1", "B2"}
    plate_vm = SimpleNamespace(get_selection=lambda: set(selection))

    toasts = []

    class DummyWin:
        def show_toast(self, message: str) -> None:
            toasts.append(message)

    ensure_called = {"value": False}

    def fake_ensure_adapter() -> bool:
        ensure_called["value"] = True
        return True

    captured = {}

    def fake_cancel_runs(payload):
        captured["payload"] = payload

    app._log = logging.getLogger("test_end_selection")
    app._toast_error = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("No error expected during end selection.")
    )
    app.win = DummyWin()
    app.plate_vm = plate_vm
    app._ensure_adapter = fake_ensure_adapter
    app.uc_cancel_runs = fake_cancel_runs
    app.progress_vm = _build_progress_snapshot()

    app._on_end_selection()

    assert ensure_called["value"] is True
    assert captured["payload"] == {
        "box_runs": {"A": ["run-a1"], "B": ["run-b"]},
        "span": "selected",
    }
    assert toasts == ["Abort requested for selected runs."]
