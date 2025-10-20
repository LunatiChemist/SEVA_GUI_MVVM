from seva.domain.entities import (
    BoxId,
    BoxSnapshot,
    GroupId,
    GroupSnapshot,
    ProgressPct,
    RunId,
    RunStatus,
    Seconds,
    WellId,
)
from seva.viewmodels.progress_vm import ProgressVM


def test_derive_well_rows_formats_and_orders_snapshot_rows() -> None:
    snapshot = GroupSnapshot(
        group=GroupId("grp-rows"),
        runs={
            WellId("B2"): RunStatus(
                run_id=RunId("run-003"),
                phase="error",
                progress=ProgressPct(10.0),
                remaining_s=Seconds(3725),
                error="Voltage spike",
            ),
            WellId("A3"): RunStatus(
                run_id=RunId("run-002"),
                phase="queued",
            ),
            WellId("A1"): RunStatus(
                run_id=RunId("run-001"),
                phase="running",
                progress=ProgressPct(50.0),
                remaining_s=Seconds(125),
            ),
        },
        boxes={},
        all_done=False,
    )

    vm = ProgressVM()
    rows = vm.derive_well_rows(snapshot)

    assert rows == [
        ("A1", "Running", 50.0, "2:05", "", "run-001"),
        ("A3", "Queued", None, "", "", "run-002"),
        ("B2", "Error", 10.0, "1:02:05", "Voltage spike", "run-003"),
    ]


def test_derive_box_rows_uses_snapshot_and_runs() -> None:
    snapshot = GroupSnapshot(
        group=GroupId("grp-box"),
        runs={
            WellId("A1"): RunStatus(
                run_id=RunId("run-a1"),
                phase="running",
                progress=ProgressPct(40.0),
                remaining_s=Seconds(90),
            ),
            WellId("A2"): RunStatus(
                run_id=RunId("run-a2"),
                phase="running",
                progress=ProgressPct(80.0),
                remaining_s=Seconds(120),
            ),
            WellId("B1"): RunStatus(
                run_id=RunId("run-b1"),
                phase="done",
                progress=ProgressPct(30.0),
            ),
        },
        boxes={
            BoxId("A"): BoxSnapshot(
                box=BoxId("A"),
                progress=ProgressPct(65.0),
                remaining_s=Seconds(120),
            )
        },
        all_done=False,
    )

    vm = ProgressVM()
    rows = vm.derive_box_rows(snapshot)

    assert rows == [
        ("A", 65.0, "2:00"),
        ("B", 30.0, ""),
    ]
