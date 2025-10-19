import pytest

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


def test_apply_snapshot_builds_dto_from_group_snapshot():
    snapshot = GroupSnapshot(
        group=GroupId("grp-42"),
        runs={
            WellId("A1"): RunStatus(
                run_id=RunId("run-1"),
                phase="running",
                progress=ProgressPct(50.0),
                remaining_s=Seconds(120),
            ),
            WellId("A2"): RunStatus(
                run_id=RunId("run-2"),
                phase="done",
                progress=ProgressPct(100.0),
                remaining_s=Seconds(0),
                error="Voltage spike",
            ),
        },
        boxes={
            BoxId("A"): BoxSnapshot(
                box=BoxId("A"),
                progress=ProgressPct(75.0),
                remaining_s=Seconds(120),
            )
        },
        all_done=False,
    )

    dto_updates = []
    activity_updates = []

    vm = ProgressVM(
        on_update_run_overview=lambda dto: dto_updates.append(dto),
        on_update_channel_activity=lambda mapping: activity_updates.append(mapping),
    )

    vm.apply_snapshot(snapshot)

    assert vm.last_snapshot is snapshot
    assert vm.run_group_id == "grp-42"

    assert len(dto_updates) == 1
    dto = dto_updates[0]
    assert dto["wells"] == [
        ("A1", "Running", 50.0, 120, "", "run-1"),
        ("A2", "Done", 100.0, 0, "Voltage spike", "run-2"),
    ]
    assert dto["boxes"]["A"]["phase"] == "Running"
    assert dto["boxes"]["A"]["progress"] == pytest.approx(75.0)
    assert dto["boxes"]["A"]["remaining"] == 120
    assert dto["boxes"]["A"]["subrun"] == ["run-1", "run-2"]

    assert activity_updates == [{"A1": "Running", "A2": "Error"}]


def test_apply_snapshot_rejects_non_group_snapshot():
    vm = ProgressVM()
    with pytest.raises(TypeError):
        vm.apply_snapshot({"wells": []})  # type: ignore[arg-type]
