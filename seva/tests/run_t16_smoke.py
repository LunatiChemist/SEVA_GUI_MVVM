import os
import sys
import threading
import time
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import requests
import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "rest_api"))

API_KEY = "test-key"
PORT = 8081
BASE_URL = f"http://127.0.0.1:{PORT}"
RUNS_ROOT = (ROOT / "smoke_runs").resolve()
RESULTS_DIR = (ROOT / "smoke_results").resolve()
SETTINGS_FILE = ROOT / "user_settings.json"

RUNS_ROOT.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StepResult:
    name: str
    status: str
    detail: str


def _parse_client_dt(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_experiment_plan(
    snapshots: Dict[str, Dict[str, str]],
    *,
    experiment: str,
    subdir: str,
    client_datetime: str,
    group_id: str,
    make_plot: bool = True,
) -> ExperimentPlan:
    meta = PlanMeta(
        experiment=experiment,
        subdir=subdir or None,
        client_dt=ClientDateTime(_parse_client_dt(client_datetime)),
        group_id=GroupId(group_id),
    )
    wells = [
        WellPlan(
            well=WellId(wid),
            mode=ModeName("CV"),
            params=CVParams.from_form(snapshot),
        )
        for wid, snapshot in snapshots.items()
    ]
    return ExperimentPlan(
        meta=meta,
        wells=wells,
        make_plot=make_plot,
    )


def install_pybeep_stub():
    module = types.ModuleType("pyBEEP")
    controller_mod = types.ModuleType("pyBEEP.controller")
    plotter_mod = types.ModuleType("pyBEEP.plotter")

    class FakeSerial:
        def __init__(self, port: str):
            self.port = port
        def close(self):
            pass

    class FakeController:
        def __init__(self, slot: int):
            self.slot = slot
            self.device = types.SimpleNamespace(
                device=types.SimpleNamespace(serial=FakeSerial(f"COM{slot}"))
            )
            self._cancel = threading.Event()
        def get_available_modes(self):
            return ["CV"]
        def get_mode_params(self, mode: str):
            return {
                "start": 0.0,
                "vertex1": 0.5,
                "vertex2": -0.5,
                "end": 0.0,
                "scan_rate": 0.1,
                "cycles": 2,
            }
        def apply_measurement(self, **kwargs):
            folder = Path(kwargs["folder"])
            folder.mkdir(parents=True, exist_ok=True)
            filename = kwargs.get("filename", "result.csv")
            steps = 8 if self.slot == 1 else 20
            for _ in range(steps):
                if self._cancel.is_set():
                    break
                time.sleep(0.1 if self.slot == 1 else 0.2)
            (folder / filename).write_text("time,current\n0,0\n")
        def abort_measurement(self):
            self._cancel.set()

    def connect_to_potentiostats():
        return [FakeController(1), FakeController(2)]

    controller_mod.connect_to_potentiostats = connect_to_potentiostats
    controller_mod.PotentiostatController = FakeController

    def _write_plot(figpath: str):
        Path(figpath).write_text("plot-placeholder\n")

    def plot_cv_cycles(csv_path, figpath=None, show=False, cycles=None):
        if figpath:
            _write_plot(figpath)
    def plot_time_series(csv_path, figpath=None, show=False):
        if figpath:
            _write_plot(figpath)

    plotter_mod.plot_cv_cycles = plot_cv_cycles
    plotter_mod.plot_time_series = plot_time_series

    module.controller = controller_mod
    module.plotter = plotter_mod

    sys.modules["pyBEEP"] = module
    sys.modules["pyBEEP.controller"] = controller_mod
    sys.modules["pyBEEP.plotter"] = plotter_mod


def start_api_server():
    os.environ["BOX_API_KEY"] = API_KEY
    os.environ["BOX_ID"] = "A"
    os.environ["RUNS_ROOT"] = str(RUNS_ROOT)
    import rest_api.app as rest_app
    config = uvicorn.Config(rest_app.app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.1)
    return server, thread


def stop_api_server(server, thread):
    server.should_exit = True
    thread.join(timeout=5)


def main():
    install_pybeep_stub()
    server = None
    thread = None
    results: List[StepResult] = []
    try:
        server, thread = start_api_server()
        headers = {"x-api-key": API_KEY}
        rescan = requests.post(f"{BASE_URL}/admin/rescan", headers=headers, timeout=5)
        results.append(StepResult("API Rescan", "PASS" if rescan.ok else "FAIL", str(rescan.json() if rescan.ok else rescan.text)))

        from seva.adapters.storage_local import StorageLocal
        from seva.viewmodels.settings_vm import SettingsVM
        from seva.usecases.save_plate_layout import SavePlateLayout
        from seva.usecases.load_plate_layout import LoadPlateLayout
from seva.usecases.start_experiment_batch import StartExperimentBatch
        from seva.usecases.poll_group_status import PollGroupStatus
        from seva.usecases.cancel_group import CancelGroup
        from seva.usecases.download_group_results import DownloadGroupResults
from seva.adapters.job_rest import JobRestAdapter
from seva.adapters.device_rest import DeviceRestAdapter
from seva.domain.ports import UseCaseError
from seva.adapters.api_errors import ApiClientError
from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    ModeName,
    PlanMeta,
    WellId,
    WellPlan,
)
from seva.domain.params import CVParams

        storage = StorageLocal(root_dir=str(ROOT))

        # Step 1: Settings save
        settings_vm = SettingsVM()
        settings_vm.api_base_urls = {"A": BASE_URL}
        settings_vm.api_keys["A"] = API_KEY
        settings_vm.set_results_dir(str(RESULTS_DIR))
        try:
            storage.save_user_settings(settings_vm.to_dict())
            results.append(StepResult("Settings Save", "PASS", f"saved to {SETTINGS_FILE}"))
        except Exception as exc:
            results.append(StepResult("Settings Save", "FAIL", f"error: {exc}"))

        # Step 2: Layout save/load
        layout_usecase = SavePlateLayout(storage)
        layout_payload: Dict[str, Dict[str, str]] = {
            "A1": {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.5",
                "cv.vertex2_v": "-0.5",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "2",
            },
            "A2": {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.3",
                "cv.vertex2_v": "-0.3",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.05",
                "cv.cycles": "3",
            },
        }
        try:
            layout_usecase("layout_smoke.json", wells=["A1", "A2"], params=layout_payload)
            loader = LoadPlateLayout(storage)
            loaded = loader("layout_smoke.json")
            flags_ok = all(loaded["well_params_map"][wid]["run_cv"] == "1" for wid in ["A1", "A2"])
            results.append(StepResult("Layout Save/Load", "PASS" if flags_ok else "FAIL", f"loaded wells={list(loaded['well_params_map'].keys())} flags_ok={flags_ok}"))
        except Exception as exc:
            results.append(StepResult("Layout Save/Load", "FAIL", f"error: {exc}"))

        # Step 3: Start wells via UseCase
        job_adapter = JobRestAdapter(base_urls={"A": BASE_URL}, api_keys={"A": API_KEY})
        device_adapter = DeviceRestAdapter(base_urls={"A": BASE_URL}, api_keys={"A": API_KEY})
        start_uc = StartExperimentBatch(job_adapter)

        plan = _build_experiment_plan(
            layout_payload,
            experiment="TestExp",
            subdir="",
            client_datetime="2025-10-15T19:00:00Z",
            group_id="grp-smoke",
        )

        try:
            start_result = start_uc(plan)
            results.append(StepResult("Start Wells", "PASS", f"started wells={start_result.started_wells} runs={start_result.per_box_runs}"))
        except (UseCaseError, ApiClientError) as exc:
            start_result = None
            results.append(StepResult("Start Wells", "FAIL", f"failed: {exc}"))

        # Step 4: Polling
        if start_result:
            poll_uc = PollGroupStatus(job_adapter)
            snapshot = poll_uc(start_result.run_group_id)
            results.append(StepResult("Polling", "PASS", f"boxes={list(snapshot['boxes'].keys())} all_done={snapshot.get('all_done')}"))
        else:
            results.append(StepResult("Polling", "SKIP", "skipped (start failed)"))

        # Step 5: Cancel
        if start_result:
            cancel_uc = CancelGroup(job_adapter)
            try:
                cancel_uc(start_result.run_group_id)
                results.append(StepResult("Cancel", "PASS", "cancel invoked"))
            except UseCaseError as exc:
                results.append(StepResult("Cancel", "FAIL", f"cancel error: {exc}"))
        else:
            results.append(StepResult("Cancel", "SKIP", "skipped (start failed)"))

        # Step 6: Files download
        if start_result:
            download_uc = DownloadGroupResults(job_adapter)
            try:
                out_dir = download_uc(start_result.run_group_id, str(RESULTS_DIR))
                results.append(StepResult("Files/Download", "PASS", f"downloaded to {out_dir}"))
            except UseCaseError as exc:
                results.append(StepResult("Files/Download", "FAIL", f"download error: {exc}"))
        else:
            results.append(StepResult("Files/Download", "SKIP", "skipped (start failed)"))

        # Step 7: Validation error scenario
        invalid_plan = _build_experiment_plan(
            {
                "A1": {
                    "run_cv": "1",
                    "cv.start_v": "0",
                    "cv.vertex1_v": "0.5",
                    "cv.vertex2_v": "-0.5",
                    "cv.final_v": "0",
                    "cv.scan_rate_v_s": "-0.1",
                    "cv.cycles": "1",
                }
            },
            experiment="TestExp",
            subdir="",
            client_datetime="2025-10-15T19:05:00Z",
            group_id="grp-smoke-invalid",
        )
        try:
            validation_result = start_uc(invalid_plan)
            started_none = not validation_result.started_wells
            status = "PASS" if started_none else "FAIL"
            detail = f"started={validation_result.started_wells}"
        except UseCaseError as exc:
            status = "FAIL"
            detail = f"error: {exc}"
        results.append(StepResult("Validation 422", status, detail))

        # Step 8: Restart persistence
        try:
            loaded_settings = storage.load_user_settings()
            persisted = loaded_settings and loaded_settings.get("results_dir") == str(RESULTS_DIR)
            results.append(StepResult("Restart Persistence", "PASS" if persisted else "FAIL", f"results_dir={loaded_settings.get('results_dir') if loaded_settings else None}"))
        except Exception as exc:
            results.append(StepResult("Restart Persistence", "FAIL", f"error: {exc}"))

    finally:
        if server and thread:
            stop_api_server(server, thread)

    for step in results:
        print(f"{step.name}|{step.status}|{step.detail}")


if __name__ == "__main__":
    main()
