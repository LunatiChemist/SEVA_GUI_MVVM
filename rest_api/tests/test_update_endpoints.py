"""REST-boundary tests for package update endpoints."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
import time
import types
import zipfile
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient


def _install_stub_modules() -> None:
    serial_mod = types.ModuleType("serial")
    serial_tools = types.ModuleType("serial.tools")
    serial_list_ports = types.ModuleType("serial.tools.list_ports")
    serial_list_ports.comports = lambda: []
    serial_tools.list_ports = serial_list_ports
    serial_mod.tools = serial_tools
    sys.modules["serial"] = serial_mod
    sys.modules["serial.tools"] = serial_tools
    sys.modules["serial.tools.list_ports"] = serial_list_ports

    pybeep = types.ModuleType("pyBEEP")
    controller = types.ModuleType("pyBEEP.controller")
    plotter = types.ModuleType("pyBEEP.plotter")

    class DummyController:
        pass

    controller.connect_to_potentiostats = lambda: []
    controller.PotentiostatController = DummyController
    plotter.plot_cv_cycles = lambda *args, **kwargs: None
    plotter.plot_time_series = lambda *args, **kwargs: None
    pybeep.controller = controller
    pybeep.plotter = plotter
    sys.modules["pyBEEP"] = pybeep
    sys.modules["pyBEEP.controller"] = controller
    sys.modules["pyBEEP.plotter"] = plotter


def _build_firmware_package(path: Path) -> Path:
    firmware_bytes = b"\x01\x02\x03\x04\x05"
    sha = hashlib.sha256(firmware_bytes).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "package_id": "pkg-test-001",
        "created_at_utc": "2026-02-13T12:00:00Z",
        "created_by": "pytest",
        "components": {
            "firmware": {
                "version": "3.4.1",
                "bin_path": "firmware/controller.bin",
                "sha256": sha,
                "flash_mode": "reuse_firmware_endpoint_logic",
            }
        },
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, indent=2))
        archive.writestr("checksums.sha256", f"{sha}  firmware/controller.bin\n")
        archive.writestr("firmware/controller.bin", firmware_bytes)
    return path


@pytest.fixture()
def api_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("NAS_CONFIG_PATH", str(tmp_path / "nas.json"))
    monkeypatch.setenv("UPDATES_ROOT", str(tmp_path / "updates"))

    _install_stub_modules()
    rest_api_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(rest_api_dir))

    if "app" in sys.modules:
        del sys.modules["app"]
    module = importlib.import_module("app")
    yield module


def _make_update_manager(module, root: Path, flash_callback: Callable[[Path], dict] | None = None):
    from update_package import PackageUpdateManager

    flash_fn = flash_callback or (lambda _path: {"ok": True, "exit_code": 0, "stdout": "", "stderr": ""})
    restart_fn = lambda: {"ok": True, "exit_code": 0, "stdout": "", "stderr": ""}
    manager = PackageUpdateManager(
        repo_root=root,
        staging_root=root / "staging",
        audit_root=root / "audit",
        flash_firmware=flash_fn,
        restart_service=restart_fn,
    )
    module.UPDATES_MANAGER = manager
    return manager


def test_updates_package_happy_path(api_module, tmp_path: Path) -> None:
    _make_update_manager(api_module, tmp_path)
    client = TestClient(api_module.app)
    package_path = _build_firmware_package(tmp_path / "update-package.zip")

    with package_path.open("rb") as handle:
        response = client.post(
            "/updates/package",
            files={"file": ("update-package.zip", handle, "application/zip")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"queued", "running"}
    update_id = payload["update_id"]
    assert update_id

    snapshot = {}
    for _ in range(80):
        poll = client.get(f"/updates/{update_id}")
        assert poll.status_code == 200
        snapshot = poll.json()
        if snapshot.get("status") in {"done", "failed"}:
            break
        time.sleep(0.05)

    assert snapshot.get("status") == "done"
    assert snapshot.get("components", {}).get("firmware") == "done"
    assert snapshot.get("restart", {}).get("ok") is True


def test_updates_package_respects_lock(api_module, tmp_path: Path) -> None:
    def slow_flash(_path: Path) -> dict:
        time.sleep(0.5)
        return {"ok": True, "exit_code": 0, "stdout": "", "stderr": ""}

    _make_update_manager(api_module, tmp_path, flash_callback=slow_flash)
    client = TestClient(api_module.app)
    package_path = _build_firmware_package(tmp_path / "update-package.zip")

    with package_path.open("rb") as first:
        first_resp = client.post(
            "/updates/package",
            files={"file": ("update-package.zip", first, "application/zip")},
        )
    assert first_resp.status_code == 200

    with package_path.open("rb") as second:
        second_resp = client.post(
            "/updates/package",
            files={"file": ("update-package.zip", second, "application/zip")},
        )
    assert second_resp.status_code == 409
    assert second_resp.json()["code"] == "updates.locked"


def test_updates_status_not_found(api_module, tmp_path: Path) -> None:
    _make_update_manager(api_module, tmp_path)
    client = TestClient(api_module.app)
    response = client.get("/updates/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "updates.not_found"
