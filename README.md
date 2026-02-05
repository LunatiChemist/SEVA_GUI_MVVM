# SEVA GUI MVVM — Electrochemistry Client & Pi Box API

**SEVA GUI MVVM** is a desktop app (Tkinter) for running electrochemical experiments on one or more Raspberry‑Pi powered “boxes” that control potentiostats.  
It follows a clean **MVVM + Hexagonal** architecture: Views are UI‑only; ViewModels hold state and commands; UseCases orchestrate workflows; Adapters talk to the REST API and local storage. The Pi side exposes a **FastAPI** service that drives `pyBEEP` to run measurements and produce data artifacts.

> Current version: **1.3.2** (GUI). License: **MIT**.

---

## Features (today)

### Core flow
- **Start → Poll → Download** for single‑box workflows:
  - Start creates **one job per well**, validates parameters **up‑front** (“all‑or‑nothing”), and posts jobs to the box.
  - Poll aggregates **run/box progress** and **remaining time** and updates the Run Overview table. 
  - Download retrieves results per **group** and mirrors the Pi folder structure locally (ZIPs are unpacked).
- **Cancel Group** and **End Selection**:
  - Cancel a whole group or only the **currently selected runs** (by `run_id`).

### Panels & buttons (what they do)
- **Well Grid**: select one or many wells; configured wells are highlighted; clipboard‑style **Copy/Paste** per mode applies the current form values (incl. flags) from the Experiment panel to multiple wells at once.
- **Experiment Panel**:
  - **Update Parameters / Copy / Paste** for CV/DC/AC/… modes (values and flags).  
  - **End Task** (group) and **End Selection** (only selected wells’ `run_id`s). 
- **Run Overview**:
  - Per‑well: **phase**, **progress %**, **remaining (s)**, **last error**, **run_id** (subrun).  
  - Per box: header shows **average progress** (optionally, box‑level remaining). 
- **Channel Activity**: shows a compact status stream; the header displays **“Updated at HH:MM:SS”** (local) after each poll.
- **Settings window**:
  - API base URL/IP per box, timeouts/intervals (flat keys only), **results directory**, optional **Enable debug logging**.  
  - **User settings** persist to JSON; **Layouts** (well configurations + flags) save/load as JSON.
- **Test Connection**: checks `/health` and `/devices` for the selected box and shows device count and metadata.

### Behind the scenes (short, not too technical)
1. **Start**  
   The GUI collects selected wells + per‑well params, runs **device‑side validation** (`/modes/{mode}/validate`) for each well, and **only if all are OK**, posts **one job per well** to `/jobs`. The Pi server estimates planned duration and starts worker threads, one per slot/device, writing CSV/PNG data into a date‑stamped folder structure.
2. **Poll**  
   The GUI calls group status, merges per‑run snapshots and computes **progress/remaining** using start time and planned duration; box headers show average progress.
3. **Download**  
   The GUI downloads **ZIPs** per group, **extracts** them, and mirrors the server’s structure into your **Results** directory. (Optionally, slot folders can be mapped to WellIDs).

---

## Architecture (60‑second tour)

- **MVVM + Hexagon**  
  - **Views** (Tkinter) = UI‑only.  
  - **ViewModels** keep UI state & commands.  
  - **UseCases** provide orchestration as composable units: start, poll, cancel, save/load layouts, download results, test connection, etc.
  - **Adapters** implement ports: `JobPort` (REST to `/jobs`, status, cancel, download), `DevicePort` (`/health`, `/devices`, `/modes`, validate), `StoragePort` (JSON layouts & settings).
- **Pi Box API** (FastAPI + pyBEEP)  
  - Endpoints: `/health`, `/devices`, `/modes`, `/modes/{mode}/params`, `/modes/{mode}/validate`, `/jobs`, `/jobs/status`, `/jobs/{run_id}`, `/jobs/{run_id}/cancel`, `/runs/{run_id}/files|file|zip`, `/admin/rescan`.  
  - The server normalizes job metadata, computes **planned duration** and **progress**, and writes a robust **run directory structure**. 

---

## Setup & Quick Start (very short)

### GUI (Windows/macOS/Linux)
1. Install Python 3.10–3.12 and the requirements (see below).  
2. Run the GUI:  
   ```bash
   python -m seva.app.main
   ```
3. In Settings, set the Pi box IP (default port 8000) and a Results directory; save.

## Pi Box API (on Raspberry Pi)

```bash
cd /opt/box
uvicorn app:app --host 0.0.0.0 --port 8000
```

ENV (optional): BOX_API_KEY="", BOX_ID="", RUNS_ROOT="/opt/box/runs"

The API exposes health, devices, modes, validation, jobs, and file download endpoints

### Configuration (short)

- **User** settings: stored as JSON using flat keys (no legacy nested dicts). 
- **Layouts**: saved/loaded as JSON (per‑well params + flags); load re‑applies configured wells and selection. 
- **Results directory**: choose your local target; the app mirrors the Pi’s run folders during download. 

### API overview (compact)

| Route                                     | Purpose                                                                |      |                              |
| ----------------------------------------- | ---------------------------------------------------------------------- | ---- | ---------------------------- |
| `GET /health`                             | Box health, device count, `box_id`.                                    |      |                              |
| `GET /devices`                            | Connected potentiostats with slot + serial.                            |      |                              |
| `GET /modes` / `GET /modes/{mode}/params` | Available modes & parameter schema.                                    |      |                              |
| `POST /modes/{mode}/validate`             | Parameter validation without touching hardware.                        |      |                              |
| `POST /jobs`                              | Start a job for selected slots; produces a `run_id`.                   |      |                              |
| `GET /jobs/status`                        | Bulk snapshot for multiple runs.                                       |      |                              |
| `GET /jobs/{run_id}`                      | Single run status; includes computed `progress_pct` and `remaining_s`. |      |                              |
| `POST /jobs/{run_id}/cancel`              | Cancel a run.                                                          |      |                              |
| `GET /runs/{run_id}/files`                | List result files.                                                     |      |                              |
| `GET /runs/{run_id}/file`                 | Download a single result file.                                         |      |                              |
| `GET /runs/{run_id}/zip`                  | Download all result files as a ZIP archive.                            |      |                              |
| `POST /admin/rescan`                      | Refresh device registry.                                               |      |                              |
|                                           |                                                                        |      |                              |

### Naming & paths (short)
The GUI creates a group id from (Experiment[__Subdir]__ClientDatetime__rnd4) and passes it to the server. The Pi stores runs under a sanitized folder hierarchy; the GUI mirrors this when downloading results.

---

## Development

- **Repository layout**  
  - `seva/` — GUI app (Views/UI only; ViewModels; UseCases; Adapters).  
  - `rest_api/` — FastAPI app for the Pi (deploys to `/opt/box/app.py` on the device).  
- **Coding standards**  
  - MVVM + Hexagon; English comments; docstrings; small PRs with tests; no client‑side fallbacks if server validates.
- **Testing**  
  - `pytest -q` from the repo root; mock adapters for UseCases (start/poll/cancel/download).  
- **Linting**  
  - (Optional) `ruff`/`black` can be added later.

---

## License

MIT
