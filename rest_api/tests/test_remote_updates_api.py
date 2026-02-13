"""Contract tests for remote update REST API endpoints."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import time
import types
import zipfile

from fastapi.testclient import TestClient
import pytest

from rest_api.update_service import compute_directory_sha256, compute_file_sha256


if sys.version_info < (3, 10):  # pragma: no cover - guarded for local legacy interpreters
    pytest.skip("rest_api contract tests require Python >= 3.10", allow_module_level=True)


def _install_pybeep_stub() -> None:
    """Provide minimal pyBEEP modules so rest_api.app can be imported in tests."""
    if "pyBEEP.controller" in sys.modules:
        return

    pybeep_module = types.ModuleType("pyBEEP")
    controller_module = types.ModuleType("pyBEEP.controller")
    plotter_module = types.ModuleType("pyBEEP.plotter")

    class _DummyPotentiostatController:
        pass

    def _connect_to_potentiostats():
        return []

    controller_module.connect_to_potentiostats = _connect_to_potentiostats
    controller_module.PotentiostatController = _DummyPotentiostatController
    plotter_module.plot_cv_cycles = lambda *args, **kwargs: None
    plotter_module.plot_time_series = lambda *args, **kwargs: None

    pybeep_module.controller = controller_module
    pybeep_module.plotter = plotter_module

    sys.modules["pyBEEP"] = pybeep_module
    sys.modules["pyBEEP.controller"] = controller_module
    sys.modules["pyBEEP.plotter"] = plotter_module


def _install_serial_stub() -> None:
    """Provide minimal pyserial modules so rest_api.app can be imported in tests."""
    if "serial.tools.list_ports" in sys.modules:
        return

    serial_module = types.ModuleType("serial")
    tools_module = types.ModuleType("serial.tools")
    list_ports_module = types.ModuleType("serial.tools.list_ports")
    list_ports_module.comports = lambda: []

    tools_module.list_ports = list_ports_module
    serial_module.tools = tools_module

    sys.modules["serial"] = serial_module
    sys.modules["serial.tools"] = tools_module
    sys.modules["serial.tools.list_ports"] = list_ports_module


def _install_legacy_module_aliases() -> None:
    """Alias package modules for absolute imports used inside rest_api.app."""
    for module_name in ("storage", "validation", "progress_utils", "update_service", "nas_smb"):
        sys.modules[module_name] = importlib.import_module(f"rest_api.{module_name}")


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a TestClient against a reloaded rest_api.app module."""
    _install_pybeep_stub()
    _install_serial_stub()
    _install_legacy_module_aliases()

    runs_root = tmp_path / "runs"
    updates_root = tmp_path / "updates"
    firmware_root = tmp_path / "firmware"
    api_target_dir = tmp_path / "api_target"
    flash_script = tmp_path / "auto_flash_linux.py"

    flash_script.write_text("print('flash ok')\n", encoding="utf-8")

    monkeypatch.setenv("RUNS_ROOT", str(runs_root))
    monkeypatch.setenv("BOX_UPDATES_ROOT", str(updates_root))
    monkeypatch.setenv("BOX_FIRMWARE_DIR", str(firmware_root))
    monkeypatch.setenv("BOX_API_TARGET_DIR", str(api_target_dir))
    monkeypatch.setenv("BOX_FLASH_SCRIPT", str(flash_script))

    sys.modules.pop("rest_api.app", None)
    app_module = importlib.import_module("rest_api.app")
    app_module = importlib.reload(app_module)

    with TestClient(app_module.app) as client:
        yield client


def _build_update_bundle(
    tmp_path: Path,
    *,
    include_manifest: bool = True,
    corrupt_checksum: bool = False,
    presence: dict[str, bool] | None = None,
) -> Path:
    """Create a synthetic remote update ZIP for endpoint tests."""
    component_presence = {
        "rest_api": True,
        "pybeep_vendor": False,
        "firmware_bundle": True,
    }
    if presence:
        component_presence.update({key: bool(value) for key, value in presence.items()})

    bundle_dir = tmp_path / f"bundle_{int(time.time() * 1000)}"
    rest_payload = bundle_dir / "payload" / "rest_api"
    pybeep_payload = bundle_dir / "payload" / "pybeep_vendor"
    firmware_payload = bundle_dir / "payload" / "firmware"
    rest_payload.mkdir(parents=True, exist_ok=True)
    pybeep_payload.mkdir(parents=True, exist_ok=True)
    firmware_payload.mkdir(parents=True, exist_ok=True)

    (rest_payload / "service.py").write_text("print('api update')\n", encoding="utf-8")
    (pybeep_payload / "vendor_marker.txt").write_text("pybeep\n", encoding="utf-8")
    firmware_bin = firmware_payload / "potentiostat.bin"
    firmware_bin.write_bytes(b"\x00\x01\x02\x03")

    rest_hash = compute_directory_sha256(rest_payload)
    pybeep_hash = compute_directory_sha256(pybeep_payload)
    firmware_hash = compute_file_sha256(firmware_bin)
    if corrupt_checksum:
        rest_hash = "0" * 64

    if include_manifest:
        manifest = {
            "manifest_version": 1,
            "bundle_version": "2026.02.13-rc1",
            "created_at_utc": "2026-02-13T10:30:00Z",
            "min_installer_api": "0.1.0",
            "paths": {
                "api_target_env_var": "BOX_API_TARGET_DIR",
                "pybeep_target": "<REPOSITORY_PATH>/vendor/pyBEEP",
            },
            "components": {
                "rest_api": {
                    "present": component_presence["rest_api"],
                    "source_dir": "payload/rest_api",
                    "sha256": rest_hash,
                    "version": "1.0.1",
                },
                "pybeep_vendor": {
                    "present": component_presence["pybeep_vendor"],
                    "source_dir": "payload/pybeep_vendor",
                    "sha256": pybeep_hash,
                    "version": "1.4.2",
                },
                "firmware_bundle": {
                    "present": component_presence["firmware_bundle"],
                    "source_file": "payload/firmware/potentiostat.bin",
                    "sha256": firmware_hash,
                    "version": "2.7.0",
                },
            },
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    zip_path = tmp_path / f"{bundle_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in bundle_dir.rglob("*"):
            archive.write(entry, arcname=entry.relative_to(bundle_dir).as_posix())
    return zip_path


def _wait_for_terminal_status(client: TestClient, update_id: str, timeout_s: float = 3.0) -> dict:
    """Poll `/updates/{id}` until done/failed/partial."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        response = client.get(f"/updates/{update_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload.get("status") in {"done", "failed", "partial"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Timed out while waiting for update {update_id}")


def test_post_updates_valid_bundle_finishes_done(api_client: TestClient, tmp_path: Path) -> None:
    """A valid update ZIP should enqueue and finish with component outcomes."""
    zip_path = _build_update_bundle(tmp_path)
    with zip_path.open("rb") as handle:
        response = api_client.post(
            "/updates",
            files={"file": (zip_path.name, handle, "application/zip")},
        )
    assert response.status_code == 200
    start_payload = response.json()
    assert start_payload["status"] == "queued"

    update_id = start_payload["update_id"]
    final_payload = _wait_for_terminal_status(api_client, update_id)
    assert final_payload["status"] == "done"

    actions = {
        item["component"]: item["action"]
        for item in final_payload.get("component_results", [])
    }
    assert actions["rest_api"] == "updated"
    assert actions["firmware_bundle"] == "updated"
    assert actions["pybeep_vendor"] == "skipped"

    version_payload = api_client.get("/version").json()
    assert "firmware_staged_version" not in version_payload
    assert version_payload["firmware_device_version"] == "unknown"


def test_post_updates_missing_manifest_returns_400(api_client: TestClient, tmp_path: Path) -> None:
    """Bundles without manifest.json should fail fast with typed 400 response."""
    zip_path = _build_update_bundle(tmp_path, include_manifest=False)
    with zip_path.open("rb") as handle:
        response = api_client.post(
            "/updates",
            files={"file": (zip_path.name, handle, "application/zip")},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "update.manifest_missing"


def test_post_updates_checksum_mismatch_returns_400(api_client: TestClient, tmp_path: Path) -> None:
    """Checksum mismatches should fail fast with typed 400 response."""
    zip_path = _build_update_bundle(tmp_path, corrupt_checksum=True)
    with zip_path.open("rb") as handle:
        response = api_client.post(
            "/updates",
            files={"file": (zip_path.name, handle, "application/zip")},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "update.checksum_mismatch"


def test_post_updates_subset_bundle_reports_skipped(api_client: TestClient, tmp_path: Path) -> None:
    """Subset bundles should complete with explicit skipped component actions."""
    zip_path = _build_update_bundle(
        tmp_path,
        presence={"rest_api": True, "pybeep_vendor": False, "firmware_bundle": False},
    )
    with zip_path.open("rb") as handle:
        response = api_client.post(
            "/updates",
            files={"file": (zip_path.name, handle, "application/zip")},
        )
    assert response.status_code == 200
    update_id = response.json()["update_id"]

    final_payload = _wait_for_terminal_status(api_client, update_id)
    assert final_payload["status"] == "done"
    actions = {
        item["component"]: item["action"]
        for item in final_payload.get("component_results", [])
    }
    assert actions["rest_api"] == "updated"
    assert actions["pybeep_vendor"] == "skipped"
    assert actions["firmware_bundle"] == "skipped"
