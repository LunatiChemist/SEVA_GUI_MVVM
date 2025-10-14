import pathlib
import threading
import time
import types

import pytest
from fastapi.testclient import TestClient

from rest_api import app as app_module


@pytest.fixture
def client(monkeypatch, tmp_path):
    class DummySerial:
        def __init__(self, port: str):
            self.port = port

        def close(self):
            pass

    class DummyController:
        def __init__(self, port: str):
            serial = DummySerial(port)
            self.device = types.SimpleNamespace(
                device=types.SimpleNamespace(serial=serial)
            )

        def get_available_modes(self):
            return ["CV"]

        def get_mode_params(self, mode: str):
            return {"mode": mode}

        def apply_measurement(self, **kwargs):
            folder = pathlib.Path(kwargs["folder"])
            relative = folder.relative_to(app_module.RUNS_ROOT)
            run_id = relative.parts[0]
            cancel_event = app_module.CANCEL_FLAGS.get(run_id)

            call_state["measurement_started"].set()

            while not call_state["allow_finish"].is_set():
                if cancel_event and cancel_event.is_set():
                    break
                time.sleep(0.01)

            (folder / "result.csv").write_text("time,current\n0,0\n")

    call_state = {
        "count": 0,
        "measurement_started": threading.Event(),
        "allow_finish": threading.Event(),
    }

    def fake_discover():
        call_state["count"] += 1
        slot = f"slot{call_state['count']:02d}"
        controller = DummyController(f"/dev/ttyACM{call_state['count']}")
        info = app_module.DeviceInfo(
            slot=slot,
            port=controller.device.device.serial.port,
            sn=f"SN{call_state['count']}",
        )
        with app_module.DEVICE_SCAN_LOCK:
            app_module.DEVICES.clear()
            app_module.DEV_META.clear()
            app_module.DEVICES[slot] = controller
            app_module.DEV_META[slot] = info
        return slot

    monkeypatch.setattr(app_module, "discover_devices", fake_discover)
    app_module.API_KEY = "test-key"
    app_module.BOX_ID = "test-box"
    app_module.RUNS_ROOT = tmp_path / "runs"
    app_module.RUNS_ROOT.mkdir(parents=True, exist_ok=True)

    with app_module.DEVICE_SCAN_LOCK:
        app_module.DEVICES.clear()
        app_module.DEV_META.clear()
    with app_module.JOB_LOCK:
        app_module.JOBS.clear()
        app_module.JOB_META.clear()
        app_module.CANCEL_FLAGS.clear()
    with app_module.SLOT_STATE_LOCK:
        app_module.SLOT_RUNS.clear()

    with TestClient(app_module.app) as test_client:
        yield test_client, call_state

    call_state["allow_finish"].set()
    for event in list(app_module.CANCEL_FLAGS.values()):
        event.set()


def test_health_uses_cached_devices(client):
    test_client, call_state = client
    startup_calls = call_state["count"]

    response = test_client.get("/health", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "devices": 1, "box_id": "test-box"}
    assert call_state["count"] == startup_calls


def test_admin_rescan_updates_cache(client):
    test_client, call_state = client

    with app_module.DEVICE_SCAN_LOCK:
        initial_devices = list(app_module.DEV_META.keys())
    startup_calls = call_state["count"]

    response = test_client.post("/admin/rescan", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    assert call_state["count"] == startup_calls + 1

    rescan_devices = response.json()["devices"]
    assert rescan_devices != initial_devices
    with app_module.DEVICE_SCAN_LOCK:
        assert rescan_devices == list(app_module.DEVICES.keys())


def test_cancel_running_job_stops_worker_and_marks_status(client):
    test_client, call_state = client

    response = test_client.post(
        "/jobs",
        headers={"x-api-key": "test-key"},
        json={
            "devices": "all",
            "mode": "CV",
            "params": {},
            "make_plot": False,
        },
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    assert call_state["measurement_started"].wait(2.0)

    cancel_response = test_client.post(
        f"/jobs/{run_id}/cancel", headers={"x-api-key": "test-key"}
    )
    assert cancel_response.status_code == 202
    assert cancel_response.json() == {"run_id": run_id, "status": "cancelled"}

    deadline = time.time() + 5
    final = None
    while time.time() < deadline:
        job_response = test_client.get(
            f"/jobs/{run_id}", headers={"x-api-key": "test-key"}
        )
        assert job_response.status_code == 200
        payload = job_response.json()
        if payload["status"] in {"cancelled", "failed"}:
            final = payload
            break
        time.sleep(0.05)

    assert final is not None, "Job did not reach a terminal state in time"
    assert final["status"] == "cancelled"
    assert all(slot["status"] == "cancelled" for slot in final["slots"])

    with app_module.JOB_LOCK:
        assert run_id not in app_module.CANCEL_FLAGS

    with app_module.SLOT_STATE_LOCK:
        for slot in final["slots"]:
            assert slot["slot"] not in app_module.SLOT_RUNS


def test_cancel_before_worker_starts_clears_queue(client, monkeypatch):
    test_client, call_state = client

    gate = threading.Event()
    original_run_one_slot = app_module._run_one_slot

    def delayed_run_one_slot(*args, **kwargs):
        gate.wait(2.0)
        original_run_one_slot(*args, **kwargs)

    monkeypatch.setattr(app_module, "_run_one_slot", delayed_run_one_slot)

    response = test_client.post(
        "/jobs",
        headers={"x-api-key": "test-key"},
        json={
            "devices": "all",
            "mode": "CV",
            "params": {},
            "make_plot": False,
        },
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    cancel_response = test_client.post(
        f"/jobs/{run_id}/cancel", headers={"x-api-key": "test-key"}
    )
    assert cancel_response.status_code == 202
    assert cancel_response.json() == {"run_id": run_id, "status": "cancelled"}

    assert not call_state["measurement_started"].is_set()

    gate.set()

    deadline = time.time() + 5
    final = None
    while time.time() < deadline:
        job_response = test_client.get(
            f"/jobs/{run_id}", headers={"x-api-key": "test-key"}
        )
        assert job_response.status_code == 200
        payload = job_response.json()
        if payload["status"] in {"cancelled", "failed"}:
            final = payload
            break
        time.sleep(0.05)

    assert final is not None, "Job did not reach a terminal state in time"
    assert final["status"] == "cancelled"
    for slot in final["slots"]:
        assert slot["status"] == "cancelled"
        assert slot["message"] == "cancelled"

    with app_module.SLOT_STATE_LOCK:
        for slot in final["slots"]:
            assert slot["slot"] not in app_module.SLOT_RUNS
