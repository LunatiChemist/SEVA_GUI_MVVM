from seva.domain.entities import (
    GroupId,
    GroupSnapshot,
    RunId,
    RunStatus,
    WellId,
)
from seva.viewmodels.progress_vm import ProgressVM


def test_map_selection_to_runs_groups_by_box_and_sorts_runs() -> None:
    snapshot = GroupSnapshot(
        group=GroupId("grp-select"),
        runs={
            WellId("A1"): RunStatus(run_id=RunId("run-1"), phase="running"),
            WellId("A2"): RunStatus(run_id=RunId("run-2"), phase="running"),
            WellId("B1"): RunStatus(run_id=RunId("run-3"), phase="queued"),
            WellId("C5"): RunStatus(run_id=RunId("run-4"), phase="done"),
        },
        boxes={},
        all_done=False,
    )

    vm = ProgressVM()
    vm.apply_snapshot(snapshot)

    mapping = vm.map_selection_to_runs([WellId("A2"), "A1", "B1", "Z9"])

    assert mapping == {
        "A": ["run-1", "run-2"],
        "B": ["run-3"],
    }
