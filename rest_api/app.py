# /opt/box/app.py
import os, uuid, threading, time, json, zipfile, io, pathlib, datetime
from typing import Optional, Literal, Dict, List
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

API_KEY = os.getenv("BOX_API_KEY", "")
RUNS_ROOT = pathlib.Path(os.getenv("RUNS_ROOT", "/opt/box/runs"))
RUNS_ROOT.mkdir(parents=True, exist_ok=True)

# ---------- Geräte-Registry ----------
class DeviceInfo(BaseModel):
    slot: str
    port: str  # z.B. /dev/ttyACM0 oder ttyACM0
    sn: Optional[str] = None

DEVICES: Dict[str, PotentiostatController] = {}   # slot -> controller
DEV_META: Dict[str, DeviceInfo] = {}              # slot -> info

def discover_devices():
    DEVICES.clear()
    DEV_META.clear()
    controllers = connect_to_potentiostats()
    ports = {p.device: p for p in serial.tools.list_ports.comports()}

    for i, ctrl in enumerate(controllers, start=1):
        slot = f"slot{i:02d}"
        DEVICES[slot] = ctrl
        try:
            port_name = ctrl.device.device.serial.port
            serial_number = ports.get(port_name).serial_number if port_name in ports else None
        except Exception:
            port_name, serial_number = "<unknown>", None

        DEV_META[slot] = DeviceInfo(slot=slot, port=str(port_name), sn=serial_number)

# ---------- Job-Modelle ----------
class JobRequest(BaseModel):
    devices: List[str] | Literal["all"] = Field(..., description='z.B. ["slot01","slot02"] oder "all"')
    mode: str = Field(..., description="z.B. 'CV', 'CA', 'LSV', ...")
    params: Dict = Field(default_factory=dict, description="Parameter für den Modus (siehe /modes/{mode}/params)")
    tia_gain: Optional[int] = 0
    sampling_interval: Optional[float] = None
    run_name: Optional[str] = None
    folder_name: Optional[str] = None      # optional eigener Ordnername
    make_plot: bool = True                 # am Ende PNG erzeugen

class SlotStatus(BaseModel):
    slot: str
    status: Literal["queued", "running", "done", "failed"]
    message: Optional[str] = None
    files: List[str] = []                  # relative Pfade

class JobStatus(BaseModel):
    run_id: str
    mode: str
    started_at: str
    status: Literal["running", "done", "failed"]
    slots: List[SlotStatus]

JOBS: Dict[str, JobStatus] = {}            # run_id -> status
JOB_LOCK = threading.Lock()

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

# ---------- Health / Geräte / Modi ----------
@app.get("/health")
def health():
    discover_devices()
    return {"ok": True, "devices": len(DEVICES)}

@app.get("/devices")
def list_devices(x_api_key: Optional[str] = Header(None)):
    discover_devices()
    require_key(x_api_key)
    return [DEV_META[s].model_dump() for s in sorted(DEV_META.keys())]

@app.get("/modes")
def list_modes(x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    # Nimm die Modi vom ersten Gerät (alle sind identisch konfiguriert)
    first = next(iter(DEVICES.values()))
    return first.get_available_modes()

@app.get("/modes/{mode}/params")
def mode_params(mode: str, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    first = next(iter(DEVICES.values()))
    try:
        return {k: str(v) for k, v in first.get_mode_params(mode).items()}
    except Exception as e:
        raise HTTPException(400, f"{e}")

# ---------- Job Worker ----------
def _run_one_slot(run_dir: pathlib.Path, slot: str, req: JobRequest, slot_status: SlotStatus):
    """Ein Slot/Device abarbeiten – blockierend im Thread."""
    ctrl = DEVICES[slot]
    # Dateien/Ordner vorbereiten
    slot_dir = run_dir / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slot}_{req.mode}.csv"
    if req.run_name:
        filename = f"{req.run_name}_{slot}_{req.mode}.csv"

    try:
        slot_status.status = "running"
        ctrl.apply_measurement(
            mode=req.mode,
            params=req.params,
            tia_gain=req.tia_gain,
            sampling_interval=req.sampling_interval,
            filename=filename,
            folder=str(slot_dir),
        )
        # Plot (optional)
        if req.make_plot:
            csv_path = slot_dir / filename
            png_path = csv_path.with_suffix(".png")
            if req.mode.upper() == "CV":
                plot_cv_cycles(str(csv_path), figpath=str(png_path), show=False, cycles=req.params.get("cycles"))
            else:
                plot_time_series(str(csv_path), figpath=str(png_path), show=False)
        # Dateien melden
        files = [str(p.relative_to(run_dir)) for p in slot_dir.iterdir() if p.is_file()]
        slot_status.files = sorted(files)
        slot_status.status = "done"
    except Exception as e:
        slot_status.status = "failed"
        slot_status.message = str(e)

def _finish_job(run_id: str):
    # Aggregierter Jobstatus aktualisieren
    job = JOBS[run_id]
    agg = "done"
    for s in job.slots:
        if s.status == "failed":
            agg = "failed"
            break
        if s.status in ("queued", "running"):
            agg = "running"
    job.status = agg

# ---------- Endpunkte: Jobs ----------
@app.post("/jobs", response_model=JobStatus)
def start_job(req: JobRequest, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)

    # Slots auswählen
    slots = sorted(DEVICES.keys()) if req.devices == "all" else [s for s in req.devices if s in DEVICES]
    if not slots:
        raise HTTPException(400, "Keine gültigen devices angegeben")

    # Ordner/Run-ID
    run_id = req.run_name or datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:6]
    run_dir = RUNS_ROOT / run_id 
    run_dir.mkdir(parents=True, exist_ok=True)
    if req.folder_name:
        (run_dir / req.folder_name).mkdir(parents=True, exist_ok=True)
        run_dir /= req.folder_name

    # Jobstatus anlegen
    with JOB_LOCK:
        JOBS[run_id] = JobStatus(
            run_id=run_id,
            mode=req.mode,
            started_at=datetime.datetime.now(timezone.utc).isoformat() + "Z",
            status="running",
            slots=[SlotStatus(slot=s, status="queued", files=[]) for s in slots],
        )

    # Threads starten
    for s in slots:
        slot_status = next(sl for sl in JOBS[run_id].slots if sl.slot == s)
        t = threading.Thread(target=_run_one_slot, args=(run_dir, s, req, slot_status), daemon=True)
        t.start()

    return JOBS[run_id]

@app.get("/jobs/{run_id}", response_model=JobStatus)
def job_status(run_id: str, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    job = JOBS.get(run_id)
    if not job:
        raise HTTPException(404, "Unbekannte run_id")
    _finish_job(run_id)
    return job

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
    return {"devices": list(DEVICES.keys())}
