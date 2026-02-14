"""Contract-focused tests for remote update use cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from seva.domain.ports import UseCaseError
from seva.domain.remote_update import UpdateSnapshot, UpdateStartReceipt
from seva.usecases.poll_remote_update import PollRemoteUpdate
from seva.usecases.start_remote_update import StartRemoteUpdate


class FakeUpdatePort:
    """Simple fake update port for use-case contract tests."""

    def __init__(self) -> None:
        self.started_calls: list[tuple[str, Path]] = []
        self.poll_calls: list[tuple[str, str]] = []

    def start_package_update(self, box_id: str, package_path: str | Path) -> UpdateStartReceipt:
        path = Path(package_path)
        self.started_calls.append((box_id, path))
        if box_id == "B":
            raise RuntimeError("busy")
        return UpdateStartReceipt(update_id=f"upd-{box_id}", status="queued", step="queued")

    def get_package_update(self, box_id: str, update_id: str) -> UpdateSnapshot:
        self.poll_calls.append((box_id, update_id))
        if box_id == "C":
            raise RuntimeError("timeout")
        status = "done" if box_id == "A" else "running"
        return UpdateSnapshot(
            update_id=update_id,
            status=status,
            step="done" if status == "done" else "apply_rest_api",
            message="ok",
            heartbeat_at="2026-02-13T12:00:00Z",
            observed_at="2026-02-13T12:00:01Z",
            started_at="2026-02-13T12:00:00Z",
            ended_at="2026-02-13T12:00:10Z" if status == "done" else None,
            components={"rest_api": "done"},
            restart={"ok": status == "done"},
            error={},
        )


def test_start_remote_update_collects_started_and_failures(tmp_path: Path) -> None:
    pkg = tmp_path / "update-package.zip"
    pkg.write_bytes(b"zip-bytes")
    port = FakeUpdatePort()
    uc = StartRemoteUpdate(port)

    result = uc(box_ids=["A", "B"], package_path=pkg)

    assert set(result.started.keys()) == {"A"}
    assert "B" in result.failures
    assert result.started["A"].update_id == "upd-A"
    assert port.started_calls == [("A", pkg), ("B", pkg)]


def test_start_remote_update_raises_when_no_box_started(tmp_path: Path) -> None:
    pkg = tmp_path / "update-package.zip"
    pkg.write_bytes(b"zip-bytes")

    class AllFailPort(FakeUpdatePort):
        def start_package_update(self, box_id: str, package_path: str | Path) -> UpdateStartReceipt:
            raise RuntimeError("down")

    uc = StartRemoteUpdate(AllFailPort())
    with pytest.raises(UseCaseError) as excinfo:
        uc(box_ids=["A"], package_path=pkg)
    assert excinfo.value.code == "UPDATE_START_FAILED"


def test_poll_remote_update_collects_status_and_failures() -> None:
    port = FakeUpdatePort()
    uc = PollRemoteUpdate(port)
    started = {
        "A": UpdateStartReceipt(update_id="upd-A", status="queued", step="queued"),
        "C": UpdateStartReceipt(update_id="upd-C", status="queued", step="queued"),
    }

    result = uc(started=started)

    assert set(result.statuses.keys()) == {"A"}
    assert result.statuses["A"].status == "done"
    assert "C" in result.failures
    assert result.all_terminal_for(started) is True

