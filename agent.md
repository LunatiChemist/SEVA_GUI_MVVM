# SEVA_GUI_MVVM — Agent Guide (v1, Variant A)

Architecture: **MVVM + Hexagonal**
Scope (Iteration 1): **Single-Box Core Flow** (Start → Poll → Download). Multi-box orchestration later.

---

## Roles
- **Pro (Tech Lead):** owns architecture, backlog, acceptance criteria, and code reviews.
- **Codex (Contributor):** implements small, testable tickets; follows standards and PR rules.
- **Maintainer:** merges, tags releases, handles CI, packaging, and dependencies.

---

## Repository Entry Points
- **GUI bootstrap:** `seva/app/main.py` (wires Views ↔ ViewModels; plan building; polling loop)
- **Views (UI-only):** `seva/app/views/*` (no domain/HTTP)
- **ViewModels:** `seva/viewmodels/*` (selection/configured wells, per-well snapshots, settings)
- **UseCases:**
  - Start: `seva/usecases/start_experiment_batch.py` (grouping, job posts, planned duration)
  - Poll: `seva/usecases/poll_group_status.py` (progress 99% cap → 100% on 'done')
  - Download: `seva/usecases/download_group_results.py`
  - Registry: `seva/usecases/group_registry.py` (planned_duration_s per run_id)
- **Adapters:** `seva/adapters/job_rest.py` (REST calls), `seva/adapters/storage_local.py`
- **Box API (local dev):** `rest_api/app.py` (FastAPI: `POST /jobs`, `GET /jobs/{run}`, `GET /runs/{run}/zip`)

---

## Coding Standards
- Python 3.11+, PEP 8, type hints on public functions/methods.
- English comments & docstrings (Google or NumPy style).
- **MVVM + Hex rules**:
  - **Views:** UI-only; expose callbacks and setters; never import requests/json/http libs.
  - **ViewModels:** state + commands; no HTTP; call UseCases only.
  - **UseCases:** orchestration + validation; **no** direct HTTP calls.
  - **Adapters:** implement `domain/ports.py` ports; I/O only; no business logic.
- Error handling: raise `UseCaseError(code, msg)` for user-presentable failures.
- Keep functions small; single responsibility; avoid global state.

---

## Variant A: Parameter Keys (UI == API)
We commit to **API-native keys in the UI** (no prefixes like `cv.`/`ea.` and no unit suffixes like `_v`, `_s`, `_v_s`).

**Key examples (phase 1 focus):**
- **CV** (Cyclic Voltammetry): `vertex1`, `vertex2`, `end`, `scan_rate`, `cycles`
- **DC/AC (Electrolysis group)**: `duration`, `charge_cutoff`, `voltage_cutoff`, `frequency`
- **LSV**: `start`, `end`, `scan_rate`
- **EIS** (example fields): `start_freq`, `end_freq`, `points`, `spacing` (`log|lin`)
- **CDL**: treat like any other current mode (no special-casing now)

> Notes:
> - Labels may continue to show units `(V)`, `(s)`, `(V/s)` — **units stay in labels, not in keys**.
> - CDL will be updated later if the API changes; for now treat it uniformly like other modes.

---

## ViewModel Snapshots (by-mode, typed)
- Persisted per-well snapshot:
  ```python
  well_params[wid] = {
    "active_mode": "CV" | "DC" | "AC" | "EIS" | "CDL",
    "flags": {"run_cv":"1","run_dc":"0","run_ac":"0","run_eis":"0","eval_cdl":"0"},
    "by_mode": {
        "CV":  { "vertex1": -0.2, "vertex2": 0.5, "end": 0.1, "scan_rate": 0.05, "cycles": 2 },
        "DC":  { "duration": 120.0, ... },
        "AC":  { "duration": 30.0, "frequency": 1.0, ... },
        "EIS": { "start_freq": 1000.0, "end_freq": 10.0, "points": 10, "spacing": "log" },
        "CDL": { "vertex_a": -0.1, "vertex_b": 0.1, "scan_rate": 0.05, "cycles": 1 }
    }
  }
