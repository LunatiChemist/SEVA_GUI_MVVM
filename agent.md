# SEVA MVVM Pro - Agent Guide (Phase 2)

## Roles
- **Pro (Product/Architect)**: Priorisiert Ziele, Architekturentscheidungen, Abnahmen.
- **Codex (Implementer)**: Liefert kleine, testbare Inkremente per PR (keine Fallbacks).
- **Maintainer**: Branches/CI/Release.

## Architecture Principles
- **MVVM + Hexagon**
  - Views: UI-only (Tkinter), keine HTTP- oder Domain-Logik.
  - ViewModels: State + Commands; Ports injiziert; kein IO.
  - UseCases: Orchestrierung; keine Adapter-Details.
  - Adapters: reine Port-Implementierungen (REST/Storage/...).

### Phase 2 Commitments
- **Ein Job pro Well** (keine Signatur-Gruppierung mehr).  :contentReference[oaicite:0]{index=0}
- **Server-berechneter Fortschritt** ist **Single Source of Truth**:
  - Server liefert `status`, `progress_pct`, `remaining_s`, `started_at`, `ended_at`.
  - Client rechnet nicht mehr selbst (kein 99%-Cap).  :contentReference[oaicite:1]{index=1}
- **Ports trennen**:
  - **DeviceRestAdapter**: `/health`, `/devices`, `/modes`, `/modes/{mode}/params`, `/modes/{mode}/validate`.
  - **JobRestAdapter**: `/jobs` (POST/GET), `/jobs/status` (Bulk), `/jobs/{id}/cancel`, `/runs/*`.
- **Keine Fallbacks/Legacy**:
  - Ersetzte Pfade/Algorithmen werden **entfernt**, nicht dupliziert.
  - Clientseitige Progress-Berechnung und Registry werden ausgebaut.  :contentReference[oaicite:2]{index=2}
- **Settings & Layouts: JSON only** (keine CSV- oder Legacy-Dateien im Client).
- **Plan carries experiment_name, subdir, client_datetime; server builds paths (S7).**
  - GUI uebergibt `results_dir`.
  - Server baut: `results_dir/ExperimentName/OptionalSubDir/ClientDateTime/Wells/<WellId>/<Mode>/...`
  - Dateiname: `ExperimentName[_SubDir]_<Datetime>_<WellId>_<Mode>.*`.  :contentReference[oaicite:3]{index=3}

## Entry Points
- GUI Bootstrap: `seva/app/main.py`  :contentReference[oaicite:4]{index=4}
- Views: `seva/app/views/*`
- ViewModels: `seva/viewmodels/*` (z. B. `ProgressVM`)  :contentReference[oaicite:5]{index=5}
- UseCases: `seva/usecases/*` (z. B. `poll_group_status.py`)  :contentReference[oaicite:6]{index=6}
- Adapters: `seva/adapters/*`
- PI-API: `app.py` (Box FastAPI)  :contentReference[oaicite:7]{index=7}
- Tests: `seva/tests/unit/*`

## Coding Standards
- PEP8, Typing, Strings/Comments **English**.
- Keine Fallbacks: Alte Pfade **entfernen**, wenn neue eingefuehrt werden.
- Saubere Fehlercodes und klare Messages.
- Each method: 1-2 line docstring plus inline comments for the key logic steps.

## Branch / PR Workflow
- Branches: `feature/<topic>`, `api/<topic>`, `refactor/<topic>`.
- Kleine PRs (< 300 LOC), Acceptance im PR-Text, gruene Tests vor Merge.
- Keine Crossover-Aenderungen: GUI/Adapter/API getrennte PRs, wenn moeglich.

## Test Strategy
- pytest Unit-Tests fuer UseCases/Adapter; Mock-Server/Mock-Adapter.
- API-Tests (FastAPI TestClient) fuer Endpoints.
- Guard-Tests sichern die No-Legacy-Regeln (`pytest -q` laesst `seva/tests/ci/test_no_legacy_paths.py` laufen); neue Invarianten bitte ebenfalls als Guard ablegen.
- **Keine** clientseitige Progress-Berechnung testen (deprecated).

## Quality Gates
- Lint: `ruff check` (pyproject baseline) and optional `flake8` spot checks; document deviations if lint is noisy.
- Typing: `mypy --config-file pyproject.toml seva rest_api` leverages the baseline (ignores missing imports by default).
- Tests/Guards: `pytest -q` runs `seva/tests/ci/test_no_legacy_paths.py` to block legacy symbols (`RunStorageInfo`, `.csv` in client adapters/usecases/views, `group_registry`, `planned_duration`, run/folder name builders).

## How to run (local)
- **API (Pi / local):**
  ```bash
  uvicorn app:app --host 0.0.0.0 --port 8000 --reload
  # All endpoints behind x-api-key (incl. /health)
  ```
