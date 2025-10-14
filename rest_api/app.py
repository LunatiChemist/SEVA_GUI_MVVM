# /opt/box/app.py
import os, uuid, threading, zipfile, io, pathlib, datetime
from typing import Optional, Literal, Dict, List, Any
from datetime import timezone
import serial.tools.list_ports
from fastapi import FastAPI, HTTPException, Header, Response
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from pyBEEP.controller import (
    connect_to_potentiostats,  # liefert List[PotentiostatController]
    PotentiostatController,
)
# Optional: vorhandene Plot-Funktionen nutzen
from pyBEEP.plotter import plot_cv_cycles, plot_time_series
from progress_utils import compute_progress, estimate_planned_duration, utcnow_iso

API_KEY = os.getenv("BOX_API_KEY", "")
BOX_ID = os.getenv("BOX_ID", "")
RUNS_ROOT = pathlib.Path(os.getenv("RUNS_ROOT", "/opt/box/runs"))
RUNS_ROOT.mkdir(parents=True, exist_ok=True)

# ---------- GerÃ¤te-Registry ----------
class DeviceInfo(BaseModel):
    slot: str
    port: str  # z.B. /dev/ttyACM0 oder ttyACM0
    sn: Optional[str] = None

DEVICES: Dict[str, PotentiostatController] = {}   # slot -> controller
DEV_META: Dict[str, DeviceInfo] = {}              # slot -> info
DEVICE_SCAN_LOCK = threading.Lock()

def discover_devices():
    with DEVICE_SCAN_LOCK:
        DEVICES.clear()
        DEV_META.clear()
        controllers = connect_to_potentiostats()
        ports = {p.device: p for p in serial.tools.list_ports.comports()}

        for i, ctrl in enumerate(controllers, start=1):
            slot = f"slot{i:02d}"
            DEVICES[slot] = ctrl
            try:
                port_name = ctrl.device.device.serial.port
                serial_info = ports.get(port_name)
                serial_number = serial_info.serial_number if serial_info else None
            except Exception:
                port_name, serial_number = "<unknown>", None

            DEV_META[slot] = DeviceInfo(slot=slot, port=str(port_name), sn=serial_number)

# ---------- Job-Modelle ----------
class JobRequest(BaseModel):
    devices: List[str] | Literal["all"] = Field(..., description='z.B. ["slot01","slot02"] oder "all"')
    mode: str = Field(..., description="z.B. 'CV', 'CA', 'LSV', ...")
    params: Dict = Field(default_factory=dict, description="Parameter fÃ¼r den Modus (siehe /modes/{mode}/params)")
    tia_gain: Optional[int] = 0
    sampling_interval: Optional[float] = None
    run_name: Optional[str] = None
    folder_name: Optional[str] = None      # optional eigener Ordnername
    make_plot: bool = True                 # am Ende PNG erzeugen

class SlotStatus(BaseModel):
    slot: str
    status: Literal["queued", "running", "done", "failed", "cancelled"]
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    message: Optional[str] = None
    files: List[str] = Field(default_factory=list)  # relative Pfade

class JobStatus(BaseModel):
    run_id: str
    mode: str
    started_at: str
    status: Literal["running", "done", "failed", "cancelled"]
    ended_at: Optional[str] = None
    slots: List[SlotStatus]
    progress_pct: int = 0
    remaining_s: Optional[int] = None


class JobStatusBulkRequest(BaseModel):
    run_ids: List[str] = Field(..., min_length=1, description="run_id list for bulk status lookup")

JOBS: Dict[str, JobStatus] = {}            # run_id -> status
JOB_LOCK = threading.Lock()
SLOT_STATE_LOCK = threading.Lock()
SLOT_RUNS: Dict[str, str] = {}             # slot -> run_id
JOB_META: Dict[str, Dict[str, Any]] = {}   # run_id -> metadata bag
CANCEL_FLAGS: Dict[str, threading.Event] = {}  # run_id -> cancel flag


def record_job_meta(run_id: str, mode: str, params: Dict[str, Any]) -> None:
    """Persist the original request parameters and derived duration estimate."""
    JOB_META[run_id] = {
        "mode": mode,
        "params": dict(params or {}),
        "planned_duration_s": estimate_planned_duration(mode, params or {}),
    }


def job_snapshot(job: JobStatus) -> JobStatus:
    copy = job.model_copy(deep=True)

    # only create/retain meta while the job is running
    meta = JOB_META.get(copy.run_id)
    if meta is None and copy.status == "running":
        meta = JOB_META[copy.run_id] = {"mode": copy.mode, "params": {}}
    elif meta is None:
        meta = {"mode": copy.mode, "params": {}}

    params = meta.get("params") if isinstance(meta.get("params"), dict) else {}
    planned = meta.get("planned_duration_s")
    if planned is None:
        planned = estimate_planned_duration(meta.get("mode") or copy.mode, params)
        # store planned only for running jobs to avoid re-populating after cleanup
        if copy.status == "running":
            meta["planned_duration_s"] = planned

    slot_payload = [slot.model_dump() for slot in copy.slots]
    metrics = compute_progress(
        status=copy.status,
        slots=slot_payload,
        started_at=copy.started_at,
        planned_duration_s=planned,
    )
    copy.progress_pct = metrics.get("progress_pct") or 0
    copy.remaining_s = metrics.get("remaining_s")
    return copy


# ---------- Startup ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    discover_devices()
    try:
        yield
    finally:
        for ctrl in DEVICES.values():
            try:
                ctrl.device.device.serial.close()
            except Exception:
                pass

app = FastAPI(title="Potentiostat Box API", version="0.1.0", lifespan=lifespan)

# ---------- Auth Helper ----------
def require_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Unauthorized")

# ---------- Health / GerÃ¤te / Modi ----------
@app.get("/health")
def health(x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    with DEVICE_SCAN_LOCK:
        device_count = len(DEVICES)
    return {"ok": True, "devices": device_count, "box_id": BOX_ID}

@app.get("/devices")
def list_devices(x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    with DEVICE_SCAN_LOCK:
        return [DEV_META[s].model_dump() for s in sorted(DEV_META.keys())]

@app.get("/modes")
def list_modes(x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    # Nimm die Modi vom ersten GerÃ¤t (alle sind identisch konfiguriert)
    with DEVICE_SCAN_LOCK:
        try:
            first = next(iter(DEVICES.values()))
        except StopIteration:
            raise HTTPException(503, "Keine Geraete registriert")
    return first.get_available_modes()

@app.get("/modes/{mode}/params")
def mode_params(mode: str, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    with DEVICE_SCAN_LOCK:
        try:
            first = next(iter(DEVICES.values()))
        except StopIteration:
            raise HTTPException(503, "Keine Geraete registriert")
    try:
        return {k: str(v) for k, v in first.get_mode_params(mode).items()}
    except Exception as e:
        raise HTTPException(400, f"{e}")

# ---------- Job Worker ----------
def _update_job_status_locked(job: Optional[JobStatus]) -> None:
    if not job:
        return

    statuses = [slot.status for slot in job.slots]
    if any(state in ("queued", "running") for state in statuses):
        job.status = "running"
        job.ended_at = None
        return

    if any(state == "failed" for state in statuses):
        job.status = "failed"
    elif any(state == "cancelled" for state in statuses):
        job.status = "cancelled"
    else:
        job.status = "done"
    job.ended_at = utcnow_iso()
    #drop transient meta once job is terminal
    JOB_META.pop(job.run_id, None)
    CANCEL_FLAGS.pop(job.run_id, None)


def _request_controller_abort(ctrl: PotentiostatController) -> None:
    """Best effort attempt to stop a running measurement on the controller."""
    for attr in (
        "abort_measurement",
        "cancel_measurement",
        "stop_measurement",
        "abort",
        "cancel",
        "stop",
    ):
        method = getattr(ctrl, attr, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass
            else:
                return

    try:
        serial = getattr(ctrl, "device", None)
        serial = getattr(serial, "device", serial)
        serial = getattr(serial, "serial", serial)
        close_method = getattr(serial, "close", None)
        if callable(close_method):
            close_method()
    except Exception:
        pass


def _run_one_slot(run_id: str, run_dir: pathlib.Path, slot: str, req: JobRequest, slot_status: SlotStatus):
    """Ein Slot/Device abarbeiten - blockierend im Thread."""
    ctrl = DEVICES[slot]
    slot_dir = run_dir / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slot}_{req.mode}.csv"
    if req.run_name:
        filename = f"{req.run_name}_{slot}_{req.mode}.csv"

    cancel_event = CANCEL_FLAGS.setdefault(run_id, threading.Event())

    if cancel_event.is_set():
        with JOB_LOCK:
            slot_status.status = "cancelled"
            if not slot_status.started_at:
                slot_status.started_at = utcnow_iso()
            slot_status.ended_at = utcnow_iso()
            slot_status.message = "cancelled"
            slot_status.files = []
            _update_job_status_locked(JOBS.get(run_id))
        with SLOT_STATE_LOCK:
            if SLOT_RUNS.get(slot) == run_id:
                del SLOT_RUNS[slot]
        return

    with JOB_LOCK:
        slot_status.status = "running"
        slot_status.started_at = utcnow_iso()
        slot_status.message = None
        _update_job_status_locked(JOBS.get(run_id))

    files: List[str] = []
    error: Optional[Exception] = None
    cancelled = False
    measurement_error: Optional[Exception] = None

    def _measurement_runner():
        nonlocal measurement_error
        try:
            ctrl.apply_measurement(
                mode=req.mode,
                params=req.params,
                tia_gain=req.tia_gain,
                sampling_interval=req.sampling_interval,
                filename=filename,
                folder=str(slot_dir),
            )
        except Exception as exc:
            measurement_error = exc

    runner_thread = threading.Thread(
        target=_measurement_runner,
        name=f"{run_id}-{slot}-measurement",
        daemon=True,
    )
    runner_thread.start()

    abort_requested = False
    while runner_thread.is_alive():
        runner_thread.join(timeout=0.2)
        if cancel_event.is_set():
            cancelled = True
            if not abort_requested:
                _request_controller_abort(ctrl)
                abort_requested = True

    runner_thread.join()
    if cancel_event.is_set():
        cancelled = True

    if cancelled:
        # treat controller exceptions as part of the cancellation flow
        measurement_error = None

    if measurement_error is not None:
        error = measurement_error
    elif not cancelled:
        csv_path = slot_dir / filename
        if req.make_plot:
            png_path = csv_path.with_suffix('.png')
            if req.mode.upper() == "CV":
                plot_cv_cycles(str(csv_path), figpath=str(png_path), show=False, cycles=req.params.get("cycles"))
            else:
                plot_time_series(str(csv_path), figpath=str(png_path), show=False)
        files = [str(p.relative_to(run_dir)) for p in slot_dir.iterdir() if p.is_file()]
    else:
        try:
            files = [str(p.relative_to(run_dir)) for p in slot_dir.iterdir() if p.is_file()]
        except Exception:
            files = []

    with JOB_LOCK:
        if cancelled:
            slot_status.status = "cancelled"
            slot_status.ended_at = utcnow_iso()
            slot_status.message = "cancelled"
            slot_status.files = sorted(files)
        elif error is None:
            slot_status.files = sorted(files)
            slot_status.status = "done"
            slot_status.ended_at = utcnow_iso()
            slot_status.message = None
        else:
            slot_status.status = "failed"
            slot_status.message = str(error)
            slot_status.ended_at = utcnow_iso()
            try:
                slot_status.files = sorted([str(p.relative_to(run_dir)) for p in slot_dir.iterdir() if p.is_file()])
            except Exception:
                slot_status.files = []
        _update_job_status_locked(JOBS.get(run_id))

    with SLOT_STATE_LOCK:
        if SLOT_RUNS.get(slot) == run_id:
            del SLOT_RUNS[slot]

# ---------- Endpunkte: Jobs ----------
@app.post("/jobs/status", response_model=List[JobStatus])
def jobs_bulk_status(req: JobStatusBulkRequest, x_api_key: Optional[str] = Header(None)):
    """Return snapshot data for multiple runs in a single call."""
    require_key(x_api_key)
    run_ids = [rid for rid in (req.run_ids or []) if rid]
    if not run_ids:
        raise HTTPException(400, "Keine run_ids angegeben")
    with JOB_LOCK:
        missing = [rid for rid in run_ids if rid not in JOBS]
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise HTTPException(404, f"Unbekannte run_ids: {missing_str}")
        # Preserve the request order when returning the enriched snapshots.
        return [job_snapshot(JOBS[rid]) for rid in run_ids]


@app.post("/jobs", response_model=JobStatus)
def start_job(req: JobRequest, x_api_key: Optional[str] = Header(None)):
    """Start a new job across selected slots and launch worker threads."""
    require_key(x_api_key)

    with DEVICE_SCAN_LOCK:
        if req.devices == "all":
            slots = sorted(DEVICES.keys())
        else:
            slots = [s for s in req.devices if s in DEVICES]
    if not slots:
        raise HTTPException(400, "Keine gueltigen devices angegeben")

    run_id = req.run_name or datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6]

    with JOB_LOCK:
        if run_id in JOBS:
            raise HTTPException(409, "run_id bereits aktiv")

    with SLOT_STATE_LOCK:
        busy = sorted(s for s in slots if s in SLOT_RUNS)
        if busy:
            raise HTTPException(409, f"Slots belegt: {', '.join(busy)}")
        for s in slots:
            SLOT_RUNS[s] = run_id

    slot_statuses = [SlotStatus(slot=s, status="queued") for s in slots]
    started_at = utcnow_iso()

    try:
        run_dir = RUNS_ROOT / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        if req.folder_name:
            (run_dir / req.folder_name).mkdir(parents=True, exist_ok=True)
            run_dir = run_dir / req.folder_name

        job = JobStatus(
            run_id=run_id,
            mode=req.mode,
            started_at=started_at,
            status="running",
            ended_at=None,
            slots=slot_statuses,
        )

        with JOB_LOCK:
            JOBS[run_id] = job
            CANCEL_FLAGS[run_id] = threading.Event()
            # Persist raw params so later progress calculations can reuse them.
            record_job_meta(run_id, req.mode, req.params or {})

        for slot_status in slot_statuses:
            t = threading.Thread(
                target=_run_one_slot,
                args=(run_id, run_dir, slot_status.slot, req, slot_status),
                daemon=True,
            )
            t.start()
    except Exception:
        with SLOT_STATE_LOCK:
            for s in slots:
                if SLOT_RUNS.get(s) == run_id:
                    del SLOT_RUNS[s]
        with JOB_LOCK:
            JOBS.pop(run_id, None)
        CANCEL_FLAGS.pop(run_id, None)
        JOB_META.pop(run_id, None)
        raise

    with JOB_LOCK:
        return job_snapshot(JOBS[run_id])


@app.post("/jobs/{run_id}/cancel", status_code=202)
def cancel_job(run_id: str, x_api_key: Optional[str] = Header(None)):
    """Signal cancellation for a running or queued job."""
    require_key(x_api_key)
    with JOB_LOCK:
        job = JOBS.get(run_id)
        if not job:
            raise HTTPException(404, "Unbekannte run_id")

        event = CANCEL_FLAGS.get(run_id)
        if event is None:
            event = CANCEL_FLAGS[run_id] = threading.Event()

        if job.status in ("done", "failed", "cancelled"):
            return {"run_id": run_id, "status": job.status}

        event.set()
        queued_slots: List[str] = []
        for slot_status in job.slots:
            if slot_status.status == "queued":
                slot_status.status = "cancelled"
                if not slot_status.started_at:
                    slot_status.started_at = utcnow_iso()
                slot_status.ended_at = utcnow_iso()
                slot_status.message = "cancelled"
                slot_status.files = []
                queued_slots.append(slot_status.slot)

        _update_job_status_locked(job)

    if queued_slots:
        with SLOT_STATE_LOCK:
            for slot in queued_slots:
                if SLOT_RUNS.get(slot) == run_id:
                    del SLOT_RUNS[slot]

    return {"run_id": run_id, "status": "cancelled"}


@app.get("/jobs/{run_id}", response_model=JobStatus)
def job_status(run_id: str, x_api_key: Optional[str] = Header(None)):
    """Return the latest status snapshot for a single run."""
    require_key(x_api_key)
    with JOB_LOCK:
        job = JOBS.get(run_id)
        if not job:
            raise HTTPException(404, "Unbekannte run_id")
        return job_snapshot(job)

@app.get("/runs/{run_id}/zip")
def get_run_zip(run_id: str, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    run_dir = RUNS_ROOT / run_id
    if not run_dir.exists():
        raise HTTPException(404, "Run nicht gefunden")
    # ZIP im Speicher bauen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in run_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(run_dir))
    buf.seek(0)
    return Response(content=buf.read(),
                    media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'})

# ---------- Admin (optional) ----------
@app.post("/admin/rescan")
def rescan(x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    discover_devices()
    with DEVICE_SCAN_LOCK:
        return {"devices": list(DEVICES.keys())}
