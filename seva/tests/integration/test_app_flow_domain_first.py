from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Sequence
import types

from seva.domain.entities import (
    BoxId,
    BoxSnapshot,
    ExperimentPlan,
    GroupId,
    GroupSnapshot,
    ModeName,
    ProgressPct,
    RunId,
    RunStatus,
    Seconds,
    WellId,
    WellPlan,
)
from seva.domain.plan_builder import build_meta, from_well_params
from seva.domain.params import CVParams
from seva.domain.ports import BoxId as PortBoxId
from seva.usecases.run_flow_coordinator import FlowHooks, RunFlowCoordinator
from seva.usecases.start_experiment_batch import StartBatchResult, WellValidationResult
from seva.viewmodels.progress_vm import ProgressVM


def _experiment_plan() -> ExperimentPlan:
    well_params = {
        "A1": {
            "run_cv": "1",
            "cv.start_v": "0",
            "cv.vertex1_v": "0.5",
            "cv.vertex2_v": "-0.5",
            "cv.final_v": "0",
            "cv.scan_rate_v_s": "0.1",
            "cv.cycles": "2",
        }
    }
    meta = build_meta(
        experiment="Integration Test",
        subdir=None,
        client_dt_local=datetime(2025, 7, 8, 9, 10, 11),
    )
    return from_well_params(
        meta=meta,
        well_params_map=well_params,
        make_plot=True,
        tia_gain=None,
        sampling_interval=None,
    )


class _JobPortStub:
    def __init__(self) -> None:
        self.started_with: ExperimentPlan | None = None

    def start_batch(self, plan: ExperimentPlan):
        self.started_with = plan
        return str(plan.meta.group_id), {"A": ["run-A1"]}

    def poll_group(self, group_id: str):
        raise NotImplementedError


class _DevicePortStub:
    def validate_mode(self, box_id: PortBoxId, mode: str, params):
        return {"ok": True, "errors": [], "warnings": []}


class _StoragePortStub:
    def save_layout(self, name, payload):
        raise NotImplementedError

    def load_layout(self, name):
        raise NotImplementedError

    def save_user_settings(self, payload):
        raise NotImplementedError

    def load_user_settings(self):
        return None


def test_domain_first_flow_validates_and_updates_progress() -> None:
    plan = _experiment_plan()
    job_port = _JobPortStub()
    device_port = _DevicePortStub()
    storage_port = _StoragePortStub()

    started_groups: List[str] = []
    started_contexts: List[str] = []
    observed_snapshots: List[GroupSnapshot] = []
    validation_calls: List[Sequence[WellValidationResult]] = []

    hooks = FlowHooks(
        on_started=lambda ctx: started_contexts.append(str(ctx.group)),
        on_snapshot=lambda snap: observed_snapshots.append(snap),
        on_validation_errors=lambda entries: validation_calls.append(entries),
    )

    def _validate(plan_input: ExperimentPlan):
        assert isinstance(plan_input, ExperimentPlan)
        return []

    def _start(plan_input: ExperimentPlan):
        assert isinstance(plan_input, ExperimentPlan)
        started_groups.append(str(plan_input.meta.group_id))
        return StartBatchResult(
            run_group_id=str(plan_input.meta.group_id),
            per_box_runs={"A": ["run-A1"]},
            started_wells=["A1"],
        )

    snapshot = GroupSnapshot(
        group=GroupId(str(plan.meta.group_id)),
        runs={
            WellId("A1"): RunStatus(
                run_id=RunId("run-A1"),
                phase="running",
                progress=ProgressPct(50.0),
                remaining_s=Seconds(120),
            )
        },
        boxes={
            BoxId("A"): BoxSnapshot(
                box=BoxId("A"),
                progress=ProgressPct(50.0),
                remaining_s=Seconds(120),
            )
        },
        all_done=False,
    )

    def _poll(group_id: str):
        assert group_id == str(plan.meta.group_id)
        return snapshot

    def _download(group_id: str, target_dir: str):
        return target_dir

    coordinator = RunFlowCoordinator(
        job_port=job_port,
        device_port=device_port,
        storage_port=storage_port,
        uc_validate_start=_validate,
        uc_start=_start,
        uc_poll=_poll,
        uc_download=_download,
        settings=types.SimpleNamespace(results_dir="results", auto_download_on_complete=False),  # type: ignore[arg-type]
        hooks=hooks,
    )

    results = coordinator.validate(plan)
    assert results == []
    ctx = coordinator.start(plan)
    assert started_groups == [str(plan.meta.group_id)]
    assert started_contexts == [str(plan.meta.group_id)]

    tick = coordinator.poll_once(ctx)
    assert tick.snapshot is snapshot
    assert observed_snapshots == [snapshot]
    assert validation_calls == []

    progress_vm = ProgressVM()
    progress_vm.apply_snapshot(snapshot)
    assert progress_vm.last_snapshot is snapshot
    assert progress_vm.run_group_id == str(plan.meta.group_id)
