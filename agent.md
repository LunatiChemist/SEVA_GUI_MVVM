# SEVA MVVM Pro — Agent Guide

## Roles
- **Pro (Product/Architect):** Priorisiert Ziele, entscheidet Architektur/Scope, reviewed PRs.
- **Codex (Implementer):** Liefert kleine, testbare Inkremente per PR.
- **Maintainer:** Branch-/Release-Management, CI, Versionierung.

## Entry points
- GUI Bootstrap: `seva/app/main.py`
- Views (UI-only): `seva/app/views/*`
- ViewModels: `seva/viewmodels/*`
- UseCases (Orchestrierung): `seva/usecases/*`
- Domain/Ports: `seva/domain/ports.py`, `seva/domain/validation.py`
- Adapter: `seva/adapters/job_rest.py`, `seva/adapters/storage_local.py`
- Backend (Box-API): `rest_api/app.py`
- Tests: `seva/tests/unit/*`

## Architecture Principles
- **MVVM + Hexagon**
  - Views: UI-only (Tkinter), keine HTTP/Domain-Logik.
  - ViewModels: State + Commands; Ports werden injiziert, kein IO.
  - UseCases: Orchestrierung (Start/Cancel/Poll/Download/Save/Load/IR).
  - Adapter: reine Port-Implementierungen (REST/Storage/...).

## Coding Standards
- PEP8, Typing; **Kommentare/Strings auf Englisch**.
- Keine Domain-/HTTP-Logik in Views.
- Kapselung: Mapping/Validation im Domain-/UseCase-Layer.
- Unit-Tests für UseCases & Mapping/Validation, GUI bleibt dünn.

## Branch & PR Workflow
- Branches: `feature/<topic>`, `fix/<topic>`.
- Kleine PRs (< ~300 LOC) mit klaren Acceptance-Kriterien.
- Squash-Merge; Commits im Imperativ, kurze Scope-Beschreibung.
- PR-Checklist:
  - Tests grün (pytest), Lint/Type ok.
  - MVVM/Hex-Regeln eingehalten (keine Logik-Leaks in Views).
  - Acceptance-Kriterien im PR-Text dokumentiert.

## Test Strategy
- **pytest** unter `seva/tests`.
- Unit-Tests: UseCases (Start, Poll), Mapping/Validation, Estimator.
- Mocks: Ports (z. B. `JobPort`) für deterministische Tests.
- Später: Integration-Tests (Mock-Server) für End-to-End.

## How to run (local)
### Backend (Box-API)
```bash
uvicorn rest_api.app:app --host 0.0.0.0 --port 8000 --reload
# ENV optional: API_KEY, RUNS_ROOT
