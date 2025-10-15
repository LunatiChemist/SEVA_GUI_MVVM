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
            run_parts = list(relative.parts)
            if "Wells" in run_parts:
                wells_index = run_parts.index("Wells")
                run_parts = run_parts[:wells_index]
            run_dir = app_module.RUNS_ROOT.joinpath(*run_parts) if run_parts else app_module.RUNS_ROOT

            run_id = None
            with app_module.RUN_DIRECTORY_LOCK:
                for candidate_id, candidate_dir in app_module.RUN_DIRECTORIES.items():
                    if candidate_dir == run_dir:
                        run_id = candidate_id
                        break
            cancel_event = app_module.CANCEL_FLAGS.get(run_id)

            call_state["measurement_started"].set()

            while not call_state["allow_finish"].is_set():
                if cancel_event and cancel_event.is_set():
                    break
                time.sleep(0.01)

            filename = kwargs.get("filename", "result.csv")
            (folder / filename).write_text("time,current\n0,0\n")

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
    app_module.configure_run_storage_root(app_module.RUNS_ROOT)
    with app_module.RUN_DIRECTORY_LOCK:
        app_module.RUN_DIRECTORIES.clear()
    index_file = app_module._run_index_path()
    if index_file.exists():
        index_file.unlink()

    with app_module.DEVICE_SCAN_LOCK:
        app_module.DEVICES.clear()
        app_module.DEV_META.clear()
    with app_module.JOB_LOCK:
        app_module.JOBS.clear()
        app_module.JOB_META.clear()
        app_module.CANCEL_FLAGS.clear()
        app_module.JOB_GROUP_IDS.clear()
        app_module.JOB_GROUP_FOLDERS.clear()
    with app_module.SLOT_STATE_LOCK:
        app_module.SLOT_RUNS.clear()

    with TestClient(app_module.app) as test_client:
        yield test_client, call_state

    call_state["allow_finish"].set()
    for event in list(app_module.CANCEL_FLAGS.values()):
        event.set()


def job_payload(**overrides):
    payload = {
        "devices": "all",
        "mode": "CV",
        "params": {},
        "make_plot": False,
        "experiment_name": "TestExperiment",
        "client_datetime": "2024-01-02T03:04:05",
    }
    payload.update(overrides)
    return payload


def wait_for_terminal_status(test_client, run_id, expected_status, timeout=5.0):
    deadline = time.time() + timeout
    last_payload = None
    while time.time() < deadline:
        response = test_client.get(f"/jobs/{run_id}", headers={"x-api-key": "test-key"})
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] in expected_status:
            return last_payload
        time.sleep(0.05)
    raise AssertionError("Job did not reach a terminal state in time")


def test_list_jobs_filters_and_payload(client):
    test_client, _ = client

    queued_job = app_module.JobStatus(
        run_id="run-queued",
        mode="CV",
        started_at="2024-01-01T00:00:00Z",
        status="running",
        ended_at=None,
        slots=[app_module.SlotStatus(slot="slot01", status="queued")],
    )
    running_job = app_module.JobStatus(
        run_id="run-running",
        mode="CA",
        started_at="2024-01-01T01:00:00Z",
        status="running",
        ended_at=None,
        slots=[app_module.SlotStatus(slot="slot02", status="running")],
    )
    done_job = app_module.JobStatus(
        run_id="run-done",
        mode="CV",
        started_at="2024-01-01T02:00:00Z",
        status="done",
        ended_at="2024-01-01T03:00:00Z",
        slots=[app_module.SlotStatus(slot="slot03", status="done")],
    )
    failed_job = app_module.JobStatus(
        run_id="run-failed",
        mode="CV",
        started_at="2024-01-01T04:00:00Z",
        status="failed",
        ended_at="2024-01-01T05:00:00Z",
        slots=[app_module.SlotStatus(slot="slot04", status="failed")],
    )

    legacy_run_dir = app_module.RUNS_ROOT / "ExpLegacy" / "LegacyGroup" / "20240101_040000"
    legacy_run_dir.mkdir(parents=True, exist_ok=True)
    app_module._record_run_directory("run-failed", legacy_run_dir)

    with app_module.JOB_LOCK:
        app_module.JOBS.clear()
        app_module.JOB_GROUP_IDS.clear()
        app_module.JOB_GROUP_FOLDERS.clear()

        app_module.JOBS[queued_job.run_id] = queued_job
        app_module.JOBS[running_job.run_id] = running_job
        app_module.JOBS[done_job.run_id] = done_job
        app_module.JOBS[failed_job.run_id] = failed_job

        app_module.JOB_GROUP_IDS[queued_job.run_id] = "Group-A"
        app_module.JOB_GROUP_IDS[running_job.run_id] = "Group-A"
        app_module.JOB_GROUP_FOLDERS[done_job.run_id] = "Group_B"

    response = test_client.get("/jobs", headers={"x-api-key": "test-key"})
    assert response.status_code == 200
    entries = {entry["run_id"]: entry for entry in response.json()}
    assert entries["run-queued"]["status"] == "queued"
    assert entries["run-queued"]["devices"] == ["slot01"]
    assert entries["run-running"]["status"] == "running"
    assert entries["run-done"]["status"] == "done"
    assert entries["run-failed"]["status"] == "failed"

    response = test_client.get(
        "/jobs",
        headers={"x-api-key": "test-key"},
        params={"state": "incomplete"},
    )
    assert response.status_code == 200
    assert {entry["run_id"] for entry in response.json()} == {"run-queued", "run-running"}

    response = test_client.get(
        "/jobs",
        headers={"x-api-key": "test-key"},
        params={"state": "completed"},
    )
    assert response.status_code == 200
    assert {entry["run_id"] for entry in response.json()} == {"run-done", "run-failed"}

    response = test_client.get(
        "/jobs",
        headers={"x-api-key": "test-key"},
        params={"group_id": "Group-A"},
    )
    assert response.status_code == 200
    assert {entry["run_id"] for entry in response.json()} == {"run-queued", "run-running"}

    response = test_client.get(
        "/jobs",
        headers={"x-api-key": "test-key"},
        params={"group_id": "Group_B"},
    )
    assert response.status_code == 200
    assert {entry["run_id"] for entry in response.json()} == {"run-done"}

    response = test_client.get(
        "/jobs",
        headers={"x-api-key": "test-key"},
        params={"group_id": "LegacyGroup", "state": "completed"},
    )
    assert response.status_code == 200
    assert {entry["run_id"] for entry in response.json()} == {"run-failed"}


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
        json=job_payload(),
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
        json=job_payload(),
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


def test_run_storage_without_subdir_uses_client_timestamp(client):
    test_client, call_state = client

    response = test_client.post(
        "/jobs",
        headers={"x-api-key": "test-key"},
        json=job_payload(
            experiment_name="Exp 01",
            subdir="",
            client_datetime="2024-03-05T10:15:30",
        ),
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    assert call_state["measurement_started"].wait(2.0)
    call_state["allow_finish"].set()

    final = wait_for_terminal_status(test_client, run_id, expected_status={"done"})
    assert final["status"] == "done"

    run_dir = app_module._resolve_run_directory(run_id)
    relative_parts = run_dir.relative_to(app_module.RUNS_ROOT).parts
    assert relative_parts == ("Exp_01", "2024-03-05T10-15-30")

    slot_dir = run_dir / "Wells" / "slot01" / "CV"
    assert slot_dir.is_dir()
    expected_file = "Exp_01_2024-03-05T10-15-30_slot01_CV.csv"
    assert (slot_dir / expected_file).exists()

    slot_files = final["slots"][0]["files"]
    assert slot_files == [f"Wells/slot01/CV/{expected_file}"]

    list_response = test_client.get(f"/runs/{run_id}/files", headers={"x-api-key": "test-key"})
    assert list_response.status_code == 200
    assert list_response.json()["files"] == [f"Wells/slot01/CV/{expected_file}"]


def test_run_storage_with_subdir_does_not_duplicate_underscores(client):
    test_client, call_state = client

    response = test_client.post(
        "/jobs",
        headers={"x-api-key": "test-key"},
        json=job_payload(
            experiment_name="Exp 02",
            subdir="Batch 01",
            client_datetime="2024-03-05 13:00:00",
        ),
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    assert call_state["measurement_started"].wait(2.0)
    call_state["allow_finish"].set()

    final = wait_for_terminal_status(test_client, run_id, expected_status={"done"})
    assert final["status"] == "done"

    run_dir = app_module._resolve_run_directory(run_id)
    relative_parts = run_dir.relative_to(app_module.RUNS_ROOT).parts
    assert relative_parts == ("Exp_02", "Batch_01", "2024-03-05_13-00-00")

    slot_dir = run_dir / "Wells" / "slot01" / "CV"
    expected_file = "Exp_02_Batch_01_2024-03-05_13-00-00_slot01_CV.csv"
    assert (slot_dir / expected_file).exists()

    slot_files = final["slots"][0]["files"]
    assert slot_files == [f"Wells/slot01/CV/{expected_file}"]
    assert "__" not in expected_file

    files_response = test_client.get(f"/runs/{run_id}/files", headers={"x-api-key": "test-key"})
    assert files_response.status_code == 200
    assert files_response.json()["files"] == [f"Wells/slot01/CV/{expected_file}"]


def test_validate_cv_params_accepts_nominal_payload(client):
    test_client, _ = client

    response = test_client.post(
        "/modes/CV/validate",
        headers={"x-api-key": "test-key"},
        json={
            "start": 0.0,
            "vertex1": 0.5,
            "vertex2": -0.5,
            "end": 0.0,
            "scan_rate": 0.5,
            "cycles": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["errors"] == []
    assert payload["warnings"] == []


def test_validate_cv_params_flags_type_and_range_errors(client):
    test_client, _ = client

    response = test_client.post(
        "/modes/CV/validate",
        headers={"x-api-key": "test-key"},
        json={
            "start": "bad",
            "vertex1": "",
            "vertex2": 0.0,
            "end": 0.0,
            "scan_rate": -1,
            "cycles": "NaN",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False

    error_codes = {entry["field"]: entry["code"] for entry in payload["errors"]}
    assert error_codes["start"] == "not_a_number"
    assert error_codes["vertex1"] == "missing_field"
    assert error_codes["scan_rate"] == "must_be_positive"
    assert error_codes["cycles"] == "not_an_integer"


@pytest.mark.parametrize(
    "mode, payload, required_fields",
    [
        ("DC", {"duration_s": 10, "voltage_v": 1.2}, []),
        ("AC", {"duration_s": 5, "frequency_hz": 1000, "voltage_v": 0.1}, []),
        ("LSV", {"start": -0.5, "end": 1.0, "scan_rate": 0.1}, []),
        ("EIS", {"freq_start_hz": 1, "freq_end_hz": 10_000, "points": 5, "spacing": "log"}, []),
        ("CDL", {"vertex_a_v": -0.2, "vertex_b_v": 0.2, "cycles": 3}, []),
    ],
)
def test_validate_other_modes_returns_placeholder_warning(client, mode, payload, required_fields):
    test_client, _ = client

    response = test_client.post(
        f"/modes/{mode}/validate",
        headers={"x-api-key": "test-key"},
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["errors"] == []
    assert len(data["warnings"]) == 1
    assert data["warnings"][0]["code"] == "not_implemented"


@pytest.mark.parametrize(
    "mode, missing_field",
    [
        ("DC", "duration_s"),
        ("AC", "frequency_hz"),
        ("LSV", "scan_rate"),
        ("EIS", "points"),
        ("CDL", "cycles"),
    ],
)
def test_validate_other_modes_require_basic_fields(client, mode, missing_field):
    test_client, _ = client

    payload = {}

    response = test_client.post(
        f"/modes/{mode}/validate",
        headers={"x-api-key": "test-key"},
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert any(issue["field"] == missing_field and issue["code"] == "missing_field" for issue in data["errors"])
