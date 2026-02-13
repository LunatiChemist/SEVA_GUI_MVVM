"""Tests for remote update adapters and use cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("requests")

from seva.adapters.api_errors import ApiClientError
from seva.adapters.update_rest import UpdateRestAdapter
from seva.domain.ports import UseCaseError
from seva.domain.update_models import (
    BoxVersionInfo,
    UpdateComponentResult,
    UpdateStartResult,
    UpdateStatus,
    UpdateStep,
)
from seva.usecases.poll_remote_update_status import PollRemoteUpdateStatus
from seva.usecases.upload_remote_update import UploadRemoteUpdate


class _FakeResponse:
    """Minimal response double compatible with adapter parsing helpers."""

    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakeSession:
    """Session double for predictable adapter endpoint calls."""

    def __init__(self, responses: dict[tuple[str, str], _FakeResponse]) -> None:
        self._responses = responses

    def post_multipart(self, url: str, *, files, timeout: int):
        _ = files
        _ = timeout
        return self._responses[("POST_MULTIPART", url)]

    def get(self, url: str, *, timeout: int):
        _ = timeout
        return self._responses[("GET", url)]

    def post(self, url: str, *, json_body=None, timeout: int):
        _ = json_body
        _ = timeout
        return self._responses[("POST", url)]


class _UpdatePortDouble:
    """Simple UpdatePort double for use-case tests."""

    def __init__(self, *, start_result=None, status_result=None, start_exc=None, status_exc=None):
        self.start_result = start_result
        self.status_result = status_result
        self.start_exc = start_exc
        self.status_exc = status_exc
        self.start_calls: list[tuple[str, Path]] = []
        self.status_calls: list[tuple[str, str]] = []

    def start_update(self, box_id: str, zip_path: str | Path):
        if self.start_exc:
            raise self.start_exc
        normalized_path = Path(zip_path)
        self.start_calls.append((box_id, normalized_path))
        return self.start_result

    def get_update_status(self, box_id: str, update_id: str):
        if self.status_exc:
            raise self.status_exc
        self.status_calls.append((box_id, update_id))
        return self.status_result

    def get_version_info(self, box_id: str):
        _ = box_id
        return BoxVersionInfo()


def test_update_rest_adapter_start_update_returns_typed_result(tmp_path: Path) -> None:
    """Adapter should parse `/updates` start response to UpdateStartResult."""
    zip_path = tmp_path / "update.zip"
    zip_path.write_bytes(b"zip")
    adapter = UpdateRestAdapter(base_urls={"A": "http://box"})
    adapter.sessions = {
        "A": _FakeSession(
            {
                ("POST_MULTIPART", "http://box/updates"): _FakeResponse(
                    200,
                    {"update_id": "upd-123", "status": "queued"},
                )
            }
        )
    }
    result = adapter.start_update("A", zip_path)
    assert result == UpdateStartResult(update_id="upd-123", status="queued")


def test_update_rest_adapter_get_update_status_returns_typed_payload() -> None:
    """Adapter should normalize status payload with typed step/component objects."""
    adapter = UpdateRestAdapter(base_urls={"A": "http://box"})
    adapter.sessions = {
        "A": _FakeSession(
            {
                ("GET", "http://box/updates/upd-123"): _FakeResponse(
                    200,
                    {
                        "update_id": "upd-123",
                        "status": "partial",
                        "started_at": "2026-02-13T10:00:00Z",
                        "finished_at": "2026-02-13T10:01:00Z",
                        "bundle_version": "2026.02.13-rc1",
                        "steps": [
                            {"step": "validate_archive", "status": "done"},
                            {"step": "apply_rest_api", "status": "done"},
                        ],
                        "component_results": [
                            {
                                "component": "rest_api",
                                "action": "updated",
                                "from_version": "1.0.0",
                                "to_version": "1.0.1",
                                "message": "ok",
                            },
                            {
                                "component": "firmware_bundle",
                                "action": "failed",
                                "error_code": "update.flash_firmware_failed",
                                "message": "disk full",
                            },
                        ],
                    },
                )
            }
        )
    }

    status = adapter.get_update_status("A", "upd-123")
    assert isinstance(status, UpdateStatus)
    assert status.status == "partial"
    assert status.steps[0] == UpdateStep(step="validate_archive", status="done", message="")
    assert status.component_results[0] == UpdateComponentResult(
        component="rest_api",
        action="updated",
        from_version="1.0.0",
        to_version="1.0.1",
        message="ok",
        error_code="",
    )
    assert status.component_results[1].error_code == "update.flash_firmware_failed"


def test_update_rest_adapter_get_version_info_returns_typed_payload() -> None:
    """Adapter should normalize `/version` payload into BoxVersionInfo."""
    adapter = UpdateRestAdapter(base_urls={"A": "http://box"})
    adapter.sessions = {
        "A": _FakeSession(
            {
                ("GET", "http://box/version"): _FakeResponse(
                    200,
                    {
                        "api": "1.0",
                        "pybeep": "1.4.2",
                        "python": "3.13.2",
                        "build": "abc123",
                        "firmware_device_version": "2.6.1",
                    },
                )
            }
        )
    }
    version = adapter.get_version_info("A")
    assert version == BoxVersionInfo(
        api="1.0",
        pybeep="1.4.2",
        python="3.13.2",
        build="abc123",
        firmware_device_version="2.6.1",
    )


def test_update_rest_adapter_raises_typed_api_errors(tmp_path: Path) -> None:
    """Adapter should raise ApiClientError on 4xx responses."""
    zip_path = tmp_path / "update.zip"
    zip_path.write_bytes(b"zip")
    adapter = UpdateRestAdapter(base_urls={"A": "http://box"})
    adapter.sessions = {
        "A": _FakeSession(
            {
                ("POST_MULTIPART", "http://box/updates"): _FakeResponse(
                    400,
                    {"code": "update.manifest_missing", "message": "missing manifest"},
                )
            }
        )
    }
    with pytest.raises(ApiClientError):
        adapter.start_update("A", zip_path)


def test_upload_remote_update_calls_port_with_valid_path(tmp_path: Path) -> None:
    """Use case should pass validated zip path into UpdatePort.start_update."""
    zip_path = tmp_path / "bundle.zip"
    zip_path.write_bytes(b"zip")
    port = _UpdatePortDouble(start_result=UpdateStartResult(update_id="id-1", status="queued"))
    usecase = UploadRemoteUpdate(port)
    result = usecase(box_id="A", zip_path=zip_path)
    assert result == UpdateStartResult(update_id="id-1", status="queued")
    assert port.start_calls == [("A", zip_path)]


def test_upload_remote_update_missing_file_raises_use_case_error(tmp_path: Path) -> None:
    """Use case should reject nonexistent ZIP path before adapter call."""
    port = _UpdatePortDouble(start_result=UpdateStartResult(update_id="id-1", status="queued"))
    usecase = UploadRemoteUpdate(port)
    missing_path = tmp_path / "does_not_exist.zip"
    with pytest.raises(UseCaseError) as exc:
        usecase(box_id="A", zip_path=missing_path)
    assert exc.value.code == "UPDATE_BUNDLE_NOT_FOUND"


def test_upload_remote_update_maps_adapter_exception_to_use_case_error(tmp_path: Path) -> None:
    """Use case should map adapter failures to stable UseCaseError codes."""
    zip_path = tmp_path / "bundle.zip"
    zip_path.write_bytes(b"zip")
    port = _UpdatePortDouble(
        start_exc=ApiClientError(
            "start_update[A]: Request failed",
            status=400,
            hint="manifest missing",
            code="update.manifest_missing",
        )
    )
    usecase = UploadRemoteUpdate(port)
    with pytest.raises(UseCaseError) as exc:
        usecase(box_id="A", zip_path=zip_path)
    assert exc.value.code == "REQUEST_FAILED"
    assert "manifest missing" in exc.value.message


def test_poll_remote_update_status_returns_typed_status() -> None:
    """Use case should proxy typed update status object."""
    expected = UpdateStatus(update_id="u1", status="running")
    port = _UpdatePortDouble(status_result=expected)
    usecase = PollRemoteUpdateStatus(port)
    result = usecase(box_id="B", update_id="u1")
    assert result is expected
    assert port.status_calls == [("B", "u1")]
