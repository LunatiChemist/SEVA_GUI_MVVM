from seva.domain.entities import GroupId, GroupSnapshot
from seva.viewmodels.progress_vm import ProgressVM


def test_apply_snapshot_sets_updated_label(monkeypatch) -> None:
    snapshot = GroupSnapshot(group=GroupId("grp-label"), runs={}, boxes={}, all_done=False)
    vm = ProgressVM()

    monkeypatch.setattr(vm, "_current_time_label", lambda: "12:34:56")

    vm.apply_snapshot(snapshot)

    assert vm.updated_at_label == "12:34:56"
