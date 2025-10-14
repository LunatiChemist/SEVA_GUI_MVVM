# SEVA MVVM Pro — Agent Guide (Phase 2)

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

### Phase‑2 Commitments
- **Ein Job pro Well** (keine Signatur-Gruppierung mehr).  :contentReference[oaicite:0]{index=0}
- **Server-berechneter Fortschritt** ist **Single Source of Truth**:
  - Server liefert `status`, `progress_pct`, `remaining_s`, `started_at`, `ended_at`.
  - Client rechnet nicht mehr selbst (kein 99%-Cap).  :contentReference[oaicite:1]{index=1}
- **Ports trennen**:
  - **DeviceRestAdapter**: `/health`, `/devices`, `/modes`, `/modes/{mode}/params`, `/modes/{mode}/validate`.
  - **JobRestAdapter**: `/jobs` (POST/GET), `/jobs/status` (Bulk), `/jobs/{id}/cancel`, `/runs/*`.
- **Keine Fallbacks/Legacy**:
  - Ersetzte Pfade/Algorithmen werden **entfernt**, nicht dupliziert.
  - Clientseitige Progress-Berechnung & Registry werden ausgebaut.  :contentReference[oaicite:2]{index=2}
- **Pfad-/Dateischema (Client-gesteuert)**:
  - GUI übergibt `results_dir`, `experiment_name`, `subdir?`, `client_datetime`.
  - Server legt ab: `results_dir/ExperimentName/OptionalSubDir/ClientDateTime/Wells/<WellId>/<Mode>/...`
  - Dateiname: `ExperimentName[_SubDir]_<Datetime>_<WellId>_<Mode>.*`.  :contentReference[oaicite:3]{index=3}

## Entry Points
- GUI Bootstrap: `seva/app/main.py`  :contentReference[oaicite:4]{index=4}
- Views: `seva/app/views/*`
- ViewModels: `seva/viewmodels/*` (z. B. `ProgressVM`)  :contentReference[oaicite:5]{index=5}
- UseCases: `seva/usecases/*` (z. B. `poll_group_status.py`)  :contentReference[oaicite:6]{index=6}
- Adapters: `seva/adapters/*`
- PI-API: `app.py` (Box FastAPI)  :contentReference[oaicite:7]{index=7}
- Tests: `seva/tests/unit/*`

## Coding Standards
- PEP8, Typing, Strings/Comments **English**.
- Keine Fallbacks: Alte Pfade **entfernen**, wenn neue eingeführt werden.
- Saubere Fehlercodes & klare Messages.
- Each new or modified method must start with at least a short docstring (1–2 lines) and include inline comments explaining key logic steps for readability.

## Branch / PR Workflow
- Branches: `feature/<topic>`, `api/<topic>`, `refactor/<topic>`.
- Kleine PRs (< 300 LOC), Acceptance im PR-Text, grüne Tests vor Merge.
- Keine Crossover-Änderungen: GUI/Adapter/API getrennte PRs, wenn möglich.

## Test Strategy
- pytest Unit-Tests für UseCases/Adapter; Mock-Server/Mock-Adapter.
- API-Tests (FastAPI TestClient) für Endpoints.
- **Keine** clientseitige Progress-Berechnung testen (deprecatet).

## How to run (local)
- **API (Pi / local):**
  ```bash
  uvicorn app:app --host 0.0.0.0 --port 8000 --reload
  # All endpoints behind x-api-key (incl. /health)