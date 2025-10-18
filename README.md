# SEVA GUI MVVM — Electrochemistry Client & Pi Box API

**SEVA GUI MVVM** is a desktop app (Tkinter) for running electrochemical experiments on one or more Raspberry‑Pi powered “boxes” that control potentiostats.  
It follows a clean **MVVM + Hexagonal** architecture: Views are UI‑only; ViewModels hold state and commands; UseCases orchestrate workflows; Adapters talk to the REST API and local storage. The Pi side exposes a **FastAPI** service that drives `pyBEEP` to run measurements and produce data artifacts. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1} :contentReference[oaicite:2]{index=2}

> Current version: **1.3.2** (GUI). License: **MIT**.

---

## Features (today)

### Core flow
- **Start → Poll → Download** for single‑box workflows:
  - Start creates **one job per well**, validates parameters **up‑front** (“all‑or‑nothing”), and posts jobs to the box. :contentReference[oaicite:3]{index=3} :contentReference[oaicite:4]{index=4}
  - Poll aggregates **run/box progress** and **remaining time** and updates the Run Overview table. :contentReference[oaicite:5]{index=5}
  - Download retrieves results per **group** and mirrors the Pi folder structure locally (ZIPs are unpacked). :contentReference[oaicite:6]{index=6}
- **Cancel Group** and **End Selection**:
  - Cancel a whole group or only the **currently selected runs** (by `run_id`). :contentReference[oaicite:7]{index=7} :contentReference[oaicite:8]{index=8}

### Panels & buttons (what they do)
- **Well Grid**: select one or many wells; configured wells are highlighted; clipboard‑style **Copy/Paste** per mode applies the current form values (incl. flags) from the Experiment panel to multiple wells at once.
- **Experiment Panel**:
  - **Update Parameters / Copy / Paste** for CV/DC/AC/… modes (values and flags).  
  - **End Task** (group) and **End Selection** (only selected wells’ `run_id`s). :contentReference[oaicite:9]{index=9}
- **Run Overview**:
  - Per‑well: **phase**, **progress %**, **remaining (s)**, **last error**, **run_id** (subrun).  
  - Per box: header shows **average progress** (optionally, box‑level remaining). :contentReference[oaicite:10]{index=10}
- **Channel Activity**: shows a compact status stream; the header displays **“Updated at HH:MM:SS”** (local) after each poll.
- **Settings window**:
  - API base URL/IP per box, timeouts/intervals (flat keys only), **results directory**, optional **Enable debug logging**.  
  - **User settings** persist to JSON; **Layouts** (well configurations + flags) save/load as JSON. :contentReference[oaicite:11]{index=11} :contentReference[oaicite:12]{index=12} :contentReference[oaicite:13]{index=13}
- **Test Connection**: checks `/health` and `/devices` for the selected box and shows device count and metadata. :contentReference[oaicite:14]{index=14}

### Behind the scenes (short, not too technical)
1. **Start**  
   The GUI collects selected wells + per‑well params, runs **device‑side validation** (`/modes/{mode}/validate`) for each well, and **only if all are OK**, posts **one job per well** to `/jobs`. The Pi server estimates planned duration and starts worker threads, one per slot/device, writing CSV/PNG data into a date‑stamped folder structure. :contentReference[oaicite:15]{index=15} :contentReference[oaicite:16]{index=16}
2. **Poll**  
   The GUI calls group status, merges per‑run snapshots and computes **progress/remaining** using start time and planned duration; box headers show average progress. :contentReference[oaicite:17]{index=17} :contentReference[oaicite:18]{index=18}
3. **Download**  
   The GUI downloads **ZIPs** per group, **extracts** them, and mirrors the server’s structure into your **Results** directory. (Optionally, slot folders can be mapped to WellIDs). :contentReference[oaicite:19]{index=19}

---

## Architecture (60‑second tour)

- **MVVM + Hexagon**  
  - **Views** (Tkinter) = UI‑only.  
  - **ViewModels** keep UI state & commands.  
  - **UseCases** provide orchestration as composable units: start, poll, cancel, save/load layouts, download results, test connection, etc. :contentReference[oaicite:20]{index=20} :contentReference[oaicite:21]{index=21} :contentReference[oaicite:22]{index=22} :contentReference[oaicite:23]{index=23} :contentReference[oaicite:24]{index=24}  
  - **Adapters** implement ports: `JobPort` (REST to `/jobs`, status, cancel, download), `DevicePort` (`/health`, `/devices`, `/modes`, validate), `StoragePort` (JSON layouts & settings). :contentReference[oaicite:25]{index=25} :contentReference[oaicite:26]{index=26}
- **Pi Box API** (FastAPI + pyBEEP)  
  - Endpoints: `/health`, `/devices`, `/modes`, `/modes/{mode}/params`, `/modes/{mode}/validate`, `/jobs`, `/jobs/status`, `/jobs/{run_id}`, `/jobs/{run_id}/cancel`, `/runs/{run_id}/files|file|zip`, `/admin/rescan`.  
  - The server normalizes job metadata, computes **planned duration** and **progress**, and writes a robust **run directory structure**. :contentReference[oaicite:27]{index=27} :contentReference[oaicite:28]{index=28} :contentReference[oaicite:29]{index=29}

---

## Setup & Quick Start (very short)

### GUI (Windows/macOS/Linux)
1. Install Python 3.10–3.12 and the requirements (see below).  
2. Run the GUI:  
   ```bash
   python -m seva.app.main
3. In Settings, set the Pi box IP (default port 8000) and a Results directory; save.

## Pi Box API (on Raspberry Pi)

cd /opt/box
uvicorn app:app --host 0.0.0.0 --port 8000
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
| `GET /runs/{run_id}/files                 | file                                                                   | zip` | List/serve/zip result files. |
| `POST /admin/rescan`                      | Refresh device registry.                                               |      |                              |
|                                           |                                                                        |      |                              |

### Naming & paths (short)
The GUI creates a group id from (Experiment[__Subdir]__ClientDatetime__rnd4) and passes it to the server. The Pi stores runs under a sanitized folder hierarchy; the GUI mirrors this when 

## Roadmap: What’s next (prioritized)

1) **Multi‑Box discovery (High)**  
   Network scan + `/health` + `/devices` per IP, then map **BoxID → A/B/C/D** in the GUI and persist the mapping. :contentReference[oaicite:38]{index=38}

2) **Orchestrator & Run Queue (High)**  
   A thin client‑side queue to coordinate starts per box/slot, avoid over‑subscription, and provide a predictable order of runs.

3) **Better Data Plotter (Low)**  
   Fast read‑only plotting directly from the extracted results hierarchy; later add analysis overlays.

4) **NAS storage & access (Medium)**  
   Pi writes directly to an SMB/NFS target; optionally a “mirror”/FTP fallback for non‑NAS setups.

5) **Server‑side progress & metrics (Very Low)**  
   Expand progress model and optionally expose `/metrics` for Prometheus‑style scraping. :contentReference[oaicite:39]{index=39}

6) **Mode extensions (Postponed, but structure‑ready)**  
   Add robust validation & normalization for **AC/DC/EIS/CDL** beyond placeholders. :contentReference[oaicite:40]{index=40}

7) **Live monitoring (Very Low)**  
   SSE/WebSocket streaming (a Stream Port exists as a placeholder in the domain). :contentReference[oaicite:41]{index=41}

8) **Codebase quality & maintainability (Very High)**  
   We will:  
   - **Improve clarity**: shorter classes, focused responsibilities, docstrings at the **top** of methods.  
   - **Streamline flows**: push repeated logic into **UseCases** or utilities; avoid duplication.  
   - **Remove over‑engineering**: eliminate redundant safety nets/fallbacks now that contracts are stable.  
   - **Reduce over‑parameterization**: prefer cohesive domain helpers; trust validated inputs.  
   - **Harmonize structure**: clearer data flow across VM → UseCase → Adapter; remove legacy branches.  
   - **Keep extensibility**: patterns that make adding features (High→Medium priority items) **easy**.

---

## Development

- **Repository layout**  
  - `seva/` — GUI app (Views/UI only; ViewModels; UseCases; Adapters).  
  - `rest_api/` — FastAPI app for the Pi (deploys to `/opt/box/app.py` on the device).  
- **Coding standards**  
  - MVVM + Hexagon; English comments; docstrings; small PRs with tests; no client‑side fallbacks if server validates. :contentReference[oaicite:42]{index=42}
- **Testing**  
  - `pytest -q` from the repo root; mock adapters for UseCases (start/poll/cancel/download).  
- **Linting**  
  - (Optional) `ruff`/`black` can be added later.

---

## License

MIT
