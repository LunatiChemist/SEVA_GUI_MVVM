# SEVA GUI MVVM — Electrochemistry Client & Pi Box API

SEVA is a desktop GUI (Tkinter) plus a Raspberry-Pi-hosted FastAPI backend for
running electrochemical experiments on one or more boxes.

The codebase follows **MVVM + Hexagonal architecture**:

- **Views** render UI only.
- **ViewModels** hold UI state and commands.
- **UseCases** orchestrate business workflows (start, poll, cancel, download).
- **Adapters** handle external I/O (HTTP, filesystem, NAS, relay, firmware).

For full developer docs, see `docs/` (MkDocs site).

---

## Current capabilities

### Core run lifecycle

- Start run groups from configured wells and mode parameters.
- Poll run status via server snapshots.
- Cancel by group or selected runs.
- Download and extract run artifacts.

### Multi-box operation

The GUI supports multiple configured boxes (A/B/C/D style mappings). Run IDs are
tracked per box and grouped under one run-group context.

### Status/progress source of truth

Progress and remaining time are computed server-side and returned in status
responses. The GUI consumes these values as authoritative snapshots.

---

## Architecture and repository layout

- `seva/`: GUI application and client-side architecture
  - `seva/app/views/*` UI views
  - `seva/viewmodels/*` viewmodels
  - `seva/usecases/*` use-case orchestration
  - `seva/adapters/*` transport/persistence adapters
  - `seva/domain/*` domain entities, ports, normalization, mapping
- `rest_api/`: FastAPI backend and worker orchestration

---

## API quick reference (selected)

- `GET /health`
- `GET /devices`
- `GET /devices/status`
- `GET /modes`
- `GET /modes/{mode}/params`
- `POST /modes/{mode}/validate`
- `POST /jobs`
- `POST /jobs/status`
- `GET /jobs`
- `GET /jobs/{run_id}`
- `POST /jobs/{run_id}/cancel`
- `GET /runs/{run_id}/files`
- `GET /runs/{run_id}/file`
- `GET /runs/{run_id}/zip`
- `POST /nas/setup`
- `GET /nas/health`
- `POST /runs/{run_id}/upload`
- `POST /firmware/flash`

For complete endpoint behavior and module details, see
`docs/classes_rest_api.md`.

---

## Quick start

### GUI (Windows/Linux/macOS)

```bash
pip install -r requirements.txt
python -m seva.app.main
```

### REST API (Linux/Raspberry Pi)

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

Optional environment variables include:

- `BOX_API_KEY`
- `BOX_ID`
- `RUNS_ROOT`
- `NAS_CONFIG_PATH`
- `BOX_BUILD` / `BOX_BUILD_ID`

---

## Reproducible dependencies

`requirements.txt` currently references `pyBEEP` via Git URL. For offline
installations, use the vendored copy in `vendor/pyBEEP` and document the local
install path in deployment procedures.

---

## Documentation map

- `docs/index.md` — entrypoint
- `docs/dev-setup.md` — local setup
- `docs/rest-api-setup.md` — backend setup on Linux/Pi
- `docs/architecture_overview.md` — MVVM + Hexagonal boundaries
- `docs/workflows_seva.md` — GUI workflow traces
- `docs/workflows_rest_api.md` — backend workflow traces
- `docs/classes_seva.md` — GUI class/module map
- `docs/classes_rest_api.md` — REST module/endpoint map
- `docs/troubleshooting.md` — common issues and fixes

---

## License

MIT
