# Execute Two-Track UI Migration: Add Web UI (Vite + React on GitHub Pages) While Keeping Tkinter Desktop UI

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agent/PLANS.md` and must be maintained according to its requirements for self-contained, novice-guiding execution.

## Purpose / Big Picture

After this change, SEVA will provide two runnable UI tracks in parallel:

1. Existing Tkinter desktop UI (kept working).
2. New modern Web UI (Vite + React), deployable on GitHub Pages.

The backend REST API remains separate and unchanged in business behavior. Users can open the Web UI in a desktop browser, enter API base URLs in Settings, save those settings locally in the browser, and run all GUI workflows (multi-box included). The Web UI will include JSON import/export for settings and developer-oriented technical errors.

This migration does not alter the core orchestration boundaries: Views render and collect input, use-case orchestration remains outside the view, adapters keep I/O concerns, and server state remains the source of truth for run status.

## Progress

- [x] (2026-02-12 00:00Z) Captured product decisions from stakeholder (all features, multi-box, desktop browser only, Vite+React, GitHub Pages, localStorage settings, JSON import/export, technical errors, two-track runtime).
- [x] (2026-02-12 04:05Z) Wrote this ExecPlan to tracked file `.agent/execplans/web-ui-migration.md` for implementation continuity.
- [x] (2026-02-12 04:05Z) Created architecture inventory mapping Tkinter responsibilities to Web views, viewmodel commands, and endpoint contracts in `docs/web_ui_migration_inventory.md`.
- [x] (2026-02-12 04:18Z) Introduced Web-specific DTO contract layer for settings, run lifecycle, diagnostics, NAS, and telemetry in `web_ui/src/domain/` plus adapter boundary mapping in `web_ui/src/adapters/http/`.
- [x] (2026-02-12 04:19Z) Implemented Web application shell, tabbed views, and viewmodel-driven command routing with no direct fetch calls in views.
- [x] (2026-02-12 04:22Z) Implemented workflow coverage for start/validate/poll/cancel/download/discovery/firmware/NAS/device status/telemetry entrypoint flows.
- [x] (2026-02-12 04:18Z) Added localStorage persistence and JSON import/export for settings (`seva.web.settings.v1`).
- [x] (2026-02-12 04:20Z) Replaced MkDocs-only GitHub Pages workflow with combined docs + web app artifact deployment to `gh-pages` (`/docs` + `/app`).
- [x] (2026-02-12 04:22Z) Updated REST API with environment-driven CORS middleware and added targeted tests in `rest_api/tests/test_cors_config.py`.
- [ ] (2026-02-12 04:26Z) Validate two-track runtime (Tkinter + Web) and finalize docs/runbooks (completed: docs/runbooks updates, `python -m pytest -q` green; remaining: `npm` build/test unavailable in this shell, Tkinter import check blocked by missing `pandas`).

## Surprises & Discoveries

- Observation: Existing GitHub Pages usage already publishes MkDocs from `gh-pages`, so Web UI deployment must explicitly avoid overwriting docs output.
  Evidence: Stakeholder statement about current MkDocs deployment strategy.
- Observation: API-key authentication is optional and currently only enforced when `BOX_API_KEY` is set, which aligns with no-API-key runtime when env is empty.
  Evidence: `require_key(...)` checks `if API_KEY and ...`.
- Observation: Two-track runtime requirement supersedes earlier delete-legacy migration preference and requires explicit parallel support strategy with clear boundaries.
- Observation: There were no existing REST API tests under `rest_api/tests/` to validate browser-specific CORS behavior.
  Evidence: `rest_api/tests/` contained only `__pycache__` during milestone-1 repository inventory.
- Observation: Domain mode builders are complete for CV/AC but placeholder-only for DC/CDL/EIS, so strict field-specific typed run forms would create false precision.
  Evidence: `seva/domain/params/dc.py`, `seva/domain/params/cdl.py`, and `seva/domain/params/eis.py` are TODO placeholders.
- Observation: Node/npm is not installed in the current shell environment, so Web build/test commands from this plan cannot execute locally.
  Evidence: `npm run build` and `npm run test -- --runInBand` both failed with `CommandNotFoundException`.
- Observation: The active Python interpreter is 3.9, while this repository targets 3.10+ syntax in `rest_api/app.py`.
  Evidence: CORS tests initially failed on import with `TypeError` for `List[str] | Literal[...]`; tests were marked skip for Python < 3.10.
- Observation: Tkinter runtime smoke import in this environment failed before GUI startup because an optional dependency is missing.
  Evidence: `python -c "import seva.app.main"` failed with `ModuleNotFoundError: No module named 'pandas'`.

## Decision Log

- Decision: Keep Tkinter and Web UI both available during and after migration (two-track operation).
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: Web stack is Vite + React and deployment target is GitHub Pages in public repo.
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: Desktop browser only for Web UI; no mobile-specific acceptance criteria for v1.
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: Preserve all current GUI feature coverage in Web UI (not a reduced MVP).
  Rationale: Explicit stakeholder requirement that only view technology changes.
  Date/Author: 2026-02-12 / Codex

- Decision: Settings behavior remains semantically unchanged; storage medium for Web is localStorage plus JSON import/export.
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: UI language is English, with technical (developer-friendly) error output.
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: REST API remains externally hosted; Web UI must be CORS/HTTPS-compatible for browser-origin requests from GitHub Pages.
  Rationale: Browser security model and stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: Define Web run planning contracts around typed per-entry DTOs (`RunEntryDto`) that carry explicit `boxId`, `slot`, `modes`, and `paramsByMode`.
  Rationale: This preserves multi-box parity while avoiding implicit box/slot derivation logic in React views.
  Date/Author: 2026-02-12 / Codex

- Decision: Keep a dedicated migration inventory document in `docs/web_ui_migration_inventory.md` as the parity checklist for implementation and validation.
  Rationale: The Web implementation spans multiple layers and needed a stable source of truth before coding milestones.
  Date/Author: 2026-02-12 / Codex

- Decision: Manually scaffold the Vite React workspace files because npm scaffolding was unavailable in this environment.
  Rationale: Preserved milestone progress while keeping architecture boundaries and deployment contracts intact.
  Date/Author: 2026-02-12 / Codex

- Decision: Guard new CORS tests with Python-version skip for <3.10.
  Rationale: Repository code already uses Python 3.10+ type syntax, and the local interpreter is Python 3.9.
  Date/Author: 2026-02-12 / Codex

## Outcomes & Retrospective

Milestones 1-6 completed, milestone 7 partially completed.

- Delivered: New Web UI workspace in `web_ui/` with typed domain contracts, adapter-normalized transport, settings localStorage import/export, run workflow orchestration, diagnostics/discovery/firmware/NAS flows, and telemetry entrypoint.
- Delivered: CORS-enabled REST API configuration in `rest_api/app.py` and targeted CORS tests in `rest_api/tests/test_cors_config.py`.
- Delivered: Unified GitHub Pages deployment workflow publishing docs at `/docs/` and web app at `/app/`.
- Delivered: Documentation updates for Web UI setup, development setup, REST API CORS variables, troubleshooting, docs nav, and README quickstart links.
- Remaining: Full local Web build/test verification requires Node/npm in the execution environment; Tkinter launch verification requires missing GUI dependency (`pandas`) in this environment.
- Lesson: Environment capability checks (node toolchain, Python version, optional GUI deps) should be verified before milestone validation to avoid late-stage validation blockers.

## Context and Orientation

Current repository structure has:

- `seva/` for the existing Tkinter GUI in MVVM + Hexagonal style.
- `rest_api/` for FastAPI service used by GUI clients.
- `docs/` and MkDocs publication already targeting GitHub Pages branch strategy.

Important migration context:

- Existing settings concepts include API base URLs, timeouts, polling parameters, and other runtime preferences.
- Existing API auth is optionally gated by env key, so â€œno API keyâ€ mode is valid when key env is unset.
- The new Web UI must not move orchestration/business flow into view components. View code should remain render/input only; orchestration continues through existing app/use-case architecture.

Definition of terms used in this plan:

- Two-track runtime: both Tkinter desktop UI and Web UI can be launched and used.
- DTO: Data Transfer Object, a typed input/output shape used at a boundary.
- CORS: Browser policy requiring server permission for cross-origin requests.
- GitHub Pages coexistence: publishing docs and Web UI together without one overwriting the other.

## Plan of Work

Milestone 1 â€” Plan materialization and mapping baseline

Create a persistent exec plan file under `.agent/execplans/` (for example `.agent/execplans/web-ui-migration.md`) and copy this plan into it. Then produce a migration inventory document in `docs/` that maps each Tkinter view region/action to its Web equivalent and command/query contracts. The inventory is a technical checklist for parity.

Expected result: a complete parity matrix and implementation worklist that can be executed without ambiguity.

Milestone 2 â€” Web app skeleton and architecture boundaries

Add a new frontend workspace (for example `web_ui/`) with Vite + React + TypeScript. Create folders that mirror MVVM intent in frontend terms:

- `src/views/` for pure rendering components.
- `src/viewmodels/` for UI state and command dispatch.
- `src/adapters/http/` for REST transport.
- `src/domain/` for DTO/type normalization.
- `src/services/` only if needed to keep orchestration outside components.

Ensure components never perform ad-hoc fetch logic directly; they call viewmodel commands.

Expected result: browser app boots locally, static shell appears, and architecture lint/rules are established.

Milestone 3 â€” Settings parity with localStorage and JSON import/export

Implement full Settings screen parity with existing logical fields and constraints. Persist settings to `localStorage` under a namespaced key. Add:

- Export settings JSON file download.
- Import settings JSON file upload and validation.

Validation must occur at boundary before state mutation. Errors are technical and explicit.

Expected result: user can input API URLs, save, reload browser and retain settings, and import/export settings JSON.

Milestone 4 â€” Run workflows parity (multi-box, server-source status)

Implement all operational workflows used by Tkinter UI:

- validate modes/parameters,
- start batch,
- poll status,
- cancel runs/groups,
- download artifacts,
- discovery,
- firmware-related paths,
- NAS-related settings/actions where UI invokes them.

All progress/state displayed in Web must come from server responses; no invented progress model.

Expected result: operational parity against current GUI behavior, including multi-box configuration and run lifecycle handling.

Milestone 5 â€” API browser compatibility updates (CORS + HTTPS-friendly behavior)

Update `rest_api/app.py` to enable configurable CORS for Web UI origins (environment-driven allowlist). Keep secure defaults and explicit documentation. Ensure preflight (`OPTIONS`) requests succeed.

Do not force API key auth if deployment mode intentionally leaves `BOX_API_KEY` empty. Preserve existing behavior.

Expected result: deployed Web UI can call hosted REST API from browser origin without CORS failures.

Milestone 6 â€” GitHub Pages coexistence with MkDocs on `gh-pages`

Implement a deterministic publish strategy so docs and Web UI coexist on Pages branch. Preferred model:

- Keep MkDocs output under a subpath (for example `/docs/`) or root, and place Web UI under a separate subpath (for example `/app/`), or vice versa.
- Use a single CI publish workflow that assembles both artifacts into one final branch tree before push.

Add base-path configuration in Vite so SPA routing/assets resolve correctly on subpath deployment.

Expected result: one Pages site serves both documentation and Web UI without clobbering either.

Milestone 7 â€” Two-track runtime hardening and documentation

Keep Tkinter startup unchanged while adding Web startup/deploy instructions. Update docs to clearly explain:

- how to run Tkinter locally,
- how to run Web UI locally,
- how to configure external API URL in settings,
- how to deploy Web UI to Pages,
- how to troubleshoot CORS/HTTPS errors.

Expected result: both UIs usable, documented, and validated.

## Concrete Steps

All commands run from `/workspace/SEVA_GUI_MVVM` unless stated otherwise.

1) Create plan and inventory artifacts

    mkdir -p .agent/execplans

   # write this execplan to .agent/execplans/web-ui-migration.md

   # create docs/web_ui_migration_inventory.md with parity mapping

2) Bootstrap Web UI workspace

    npm create vite@latest web_ui -- --template react-ts
    cd web_ui
    npm install
    npm run build
    cd ..

3) Implement architecture folders and base modules

    mkdir -p web_ui/src/{views,viewmodels,adapters/http,domain,services,settings}

   # add typed settings DTO schemas and mapping utilities

4) Implement settings persistence/import/export

   # add localStorage adapter module

   # add JSON import/export utilities

    cd web_ui
    npm run build
    npm run test -- --runInBand   # if test runner configured
    cd ..

5) Implement workflow integration

   # wire run start/poll/cancel/download + other feature endpoints

   # keep components render-only and dispatch through viewmodels

    cd web_ui
    npm run build
    cd ..

6) REST API CORS update and tests

   # modify rest_api/app.py with CORSMiddleware config from env allowlist

    python -m pytest -q

   # add/execute targeted tests for CORS and endpoint compatibility if test suite exists

7) GitHub Pages assembly strategy

   # create CI workflow to build mkdocs and web_ui and merge artifacts into gh-pages tree

   # verify local artifact layout before pushing workflow changes

8) Manual acceptance checks

   # Run API externally or local dev equivalent

   # Run web_ui dev server

    cd web_ui
    npm run dev

   # In browser

   # - open app

   # - set external API URLs in settings

   # - save and reload

   # - start/poll/cancel workflow

   # - export settings JSON, clear storage, import JSON, verify restoration

Expected successful transcripts/signals:

- `npm run build` exits 0 for web_ui.
- Browser network tab shows successful API requests (no CORS errors).
- Settings survive reload via localStorage.
- Import/export reproduces same settings state.
- Tkinter app still launches and functions.

## Validation and Acceptance

Acceptance criteria (must all pass):

1. Two-track operation:
   - Tkinter desktop UI starts and remains functional.
   - Web UI starts and remains functional.

2. Feature parity:
   - All major existing GUI workflows are accessible in Web UI and operate against same backend semantics.

3. Multi-box parity:
   - Web settings and run flows support multiple box URLs and concurrent workflow semantics equivalent to current behavior.

4. Settings behavior:
   - Save semantics unchanged in meaning.
   - localStorage persistence works.
   - JSON export/import roundtrip reproduces settings.

5. Browser compatibility:
   - Hosted Web UI on GitHub Pages can call external REST API with no CORS-blocked requests.
   - HTTPS deployment path works for browser security constraints.

6. Technical errors:
   - Errors exposed to users are explicit and developer-oriented; no swallowed exceptions in UI logic.

7. GitHub Pages coexistence:
   - MkDocs and Web UI are both accessible after deployment from shared `gh-pages` publication pipeline.

## Idempotence and Recovery

- Each milestone is additive and can be rerun safely.
- If a milestone breaks, revert only changed files for that milestone and rerun checks.
- Keep Tkinter path untouched until Web parity checks are green.
- For deployment pipeline edits, verify generated artifact tree locally before publishing.
- For settings import, reject invalid JSON with clear technical error and preserve current state (no partial overwrite).

## Artifacts and Notes

Implementation artifacts produced:

- `.agent/execplans/web-ui-migration.md` (living copy of this plan).
- `docs/web_ui_migration_inventory.md` (feature parity map).
- `web_ui/` (Vite + React TypeScript workspace with MVVM-style layering).
- Updated `rest_api/app.py` for CORS configuration.
- Updated `.github/workflows/docs.yml` for docs + web app Pages deployment.
- Documentation updates in `docs/` and `README.md`.

Validation evidence captured during execution:

- `cd web_ui && npm run build`

    npm : Die Benennung "npm" wurde nicht als Name eines Cmdlet ... erkannt.
    FullyQualifiedErrorId : CommandNotFoundException

- `cd web_ui && npm run test -- --runInBand`

    npm : Die Benennung "npm" wurde nicht als Name eines Cmdlet ... erkannt.
    FullyQualifiedErrorId : CommandNotFoundException

- `python -m pytest -q`

    ........sss                                                              [100%]
    8 passed, 3 skipped in 0.61s

- `python -c "import seva.app.main; print('seva.app.main import ok')"`

    ModuleNotFoundError: No module named 'pandas'

Evidence gaps to close on a machine with full toolchain:

- Run `npm install`, `npm run build`, and `npm run test` inside `web_ui/`.
- Launch `python -m seva.app.main` after installing optional GUI dependency chain (including `pandas`).

## Interfaces and Dependencies

Frontend dependencies:

- Vite + React + TypeScript.
- Minimal additional libraries for routing/state only when needed.
- Optional schema validation library for settings DTO validation at boundary.

Backend dependencies:

- FastAPI existing app remains primary API surface.
- Add CORS middleware configuration driven by environment variables, for example:
  - `CORS_ALLOW_ORIGINS` comma-separated origins.
  - Optional `CORS_ALLOW_CREDENTIALS`, methods, headers controls with sane defaults.

Configuration interfaces:

- Web settings key in localStorage, versioned (for migration safety), for example `seva.web.settings.v1`.
- Settings import/export schema version field to allow future upgrades.

Boundary contracts:

- Views: pure render and user input capture.
- ViewModels: hold UI state and dispatch commands.
- Adapters: HTTP request execution and transport error mapping.
- No raw untyped payloads in viewmodel orchestration paths beyond adapter boundary normalization.

---

Plan revision note: This revision incorporates stakeholder-confirmed constraints: full feature parity, multi-box support, desktop browser only, Vite+React, GitHub Pages public deployment, external REST API, no API key required, CORS/HTTPS readiness, localStorage persistence with JSON import/export, English modernized UI, technical errors, and mandatory two-track operation (Tkinter + Web).

Plan revision note (2026-02-12 04:05Z): Marked Milestone 1 complete, recorded architecture inventory artifact paths, and added implementation discoveries/decisions that affect upcoming DTO, workflow, and testing milestones.

Plan revision note (2026-02-12 04:26Z): Updated living sections after implementing milestones 2-7 work, added validation evidence snippets, and documented remaining environment-based verification gaps.

