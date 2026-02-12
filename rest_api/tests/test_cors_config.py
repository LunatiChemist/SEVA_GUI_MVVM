import importlib.util
import os
import sys
import types
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="rest_api/app.py uses Python 3.10+ type-union syntax",
)


def _install_dependency_stubs() -> None:
    serial_module = types.ModuleType("serial")
    serial_tools = types.ModuleType("serial.tools")
    serial_list_ports = types.ModuleType("serial.tools.list_ports")
    serial_list_ports.comports = lambda: []
    serial_tools.list_ports = serial_list_ports
    serial_module.tools = serial_tools

    nas_module = types.ModuleType("nas_smb")

    class DummyNASManager:
        def __init__(self, *args, **kwargs):
            pass

        def start_background(self):
            return None

        def setup(self, **kwargs):
            return {"ok": True, "config": kwargs}

        def health(self):
            return {"ok": True}

        def enqueue_upload(self, run_id):
            return True

    nas_module.NASManager = DummyNASManager

    pybeep_module = types.ModuleType("pyBEEP")
    pybeep_controller = types.ModuleType("pyBEEP.controller")
    pybeep_controller.connect_to_potentiostats = lambda: []

    class DummyController:
        pass

    pybeep_controller.PotentiostatController = DummyController
    pybeep_plotter = types.ModuleType("pyBEEP.plotter")
    pybeep_plotter.plot_cv_cycles = lambda *args, **kwargs: None
    pybeep_plotter.plot_time_series = lambda *args, **kwargs: None

    sys.modules["serial"] = serial_module
    sys.modules["serial.tools"] = serial_tools
    sys.modules["serial.tools.list_ports"] = serial_list_ports
    sys.modules["nas_smb"] = nas_module
    sys.modules["pyBEEP"] = pybeep_module
    sys.modules["pyBEEP.controller"] = pybeep_controller
    sys.modules["pyBEEP.plotter"] = pybeep_plotter


def _load_app(tmp_path: Path, cors_origins: str):
    _install_dependency_stubs()
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    module_name = f"rest_api_app_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    old_runs = Path(tmp_path / "runs")
    old_cfg = Path(tmp_path / "nas_smb.json")
    os_environ = {
        "RUNS_ROOT": str(old_runs),
        "NAS_CONFIG_PATH": str(old_cfg),
        "CORS_ALLOW_ORIGINS": cors_origins,
        "CORS_ALLOW_METHODS": "GET,POST,OPTIONS",
        "CORS_ALLOW_HEADERS": "Authorization,Content-Type,X-API-Key",
    }

    previous = {key: os.environ.get(key) for key in os_environ}
    try:
        for key, value in os_environ.items():
            os.environ[key] = value
        sys.path.insert(0, str(app_path.parent))
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == str(app_path.parent):
            sys.path.pop(0)
        for key, previous_value in previous.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value
    return module.app


def test_preflight_allows_configured_origin(tmp_path: Path):
    app = _load_app(tmp_path, "https://lab-ui.example")
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://lab-ui.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "https://lab-ui.example"


def test_preflight_rejects_unlisted_origin(tmp_path: Path):
    app = _load_app(tmp_path, "https://trusted.example")
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in {400, 405}
    assert "access-control-allow-origin" not in response.headers


def test_no_cors_headers_when_origins_not_configured(tmp_path: Path):
    app = _load_app(tmp_path, "")
    client = TestClient(app)
    response = client.get("/health", headers={"Origin": "https://lab-ui.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
