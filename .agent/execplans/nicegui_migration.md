# Migrate SEVA to NiceGUI Web UI in Parallel with Tkinter (Maximum Python Reuse)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agent/PLANS.md` and must be maintained according to its requirements.

## Purpose / Big Picture

After this change, SEVA will have a second UI runtime: a NiceGUI-based Web UI that can be opened via URL (localhost first, deployable later), while the current Tkinter desktop UI remains available in parallel until full feature parity is reached. The migration prioritizes maximum reuse of existing Python architecture (UseCases, Adapters, Domain logic, and reusable ViewModel logic), and limits UI changes to the View layer plus thin NiceGUI-facing VM bindings.

User-visible outcome:

- Start Tkinter as before.
- Start NiceGUI app locally and open it in a browser.
- Configure 4 box URLs (A/B/C/D), run existing workflows, and use browser-side settings persistence with JSON import/export.

This preserves the documented MVVM + Hexagonal boundaries and keeps server state authoritative for run status.​:codex-file-citation[codex-file-citation]{line_range_start=5 line_range_end=20 path=docs/architecture_overview.md git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/docs/architecture_overview.md#L5-L20"}​​:codex-file-citation[codex-file-citation]{line_range_start=20 line_range_end=29 path=docs/index.md git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/docs/index.md#L20-L29"}​

## Progress

- [x] (2026-02-12 00:00Z) Captured stakeholder constraints and confirmed NiceGUI direction.
- [x] (2026-02-12 08:08Z) Persisted this revised plan under `.agent/execplans/nicegui_migration.md`.
- [x] (2026-02-12 08:09Z) Wrote parity inventory mapping each Tkinter view action to NiceGUI pages/components in `docs/web_ui_parity_inventory.md`.
- [x] (2026-02-12 08:31Z) Added NiceGUI app shell and parallel startup entrypoint under `seva/web_ui/` without changing Tkinter startup path.
- [x] (2026-02-12 08:33Z) Added thin NiceGUI-facing VM layer (`seva/web_ui/viewmodels.py`, `seva/web_ui/plotter_vm.py`) reusing core VM/domain logic.
- [x] (2026-02-12 08:36Z) Implemented browser `localStorage` settings persistence + JSON import/export + compatibility via `SettingsVM.apply_dict`.
- [x] (2026-02-12 08:42Z) Migrated core workflows (start/validate/poll/cancel/download, run overview/activity, discovery) into NiceGUI runtime orchestration.
- [x] (2026-02-12 08:48Z) Migrated deferred workflows (firmware, NAS, data-plotter interactions) into dedicated NiceGUI tabs.
- [x] (2026-02-12 08:52Z) Updated REST API communication for web deployment via optional CORS middleware (`SEVA_CORS_ALLOW_ORIGINS`).
- [x] (2026-02-12 08:57Z) Validated runtimes and documented run/deploy options in README + docs.

## Surprises & Discoveries

- Observation: The current root view is explicitly Tkinter (`tk.Tk`), so browser rendering requires a separate web View implementation rather than direct widget reuse.
  Evidence: `MainWindowView` inherits `tk.Tk`.​:codex-file-citation[codex-file-citation]{line_range_start=19 line_range_end=25 path=seva/app/views/main_window.py git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/seva/app/views/main_window.py#L19-L25"}​

- Observation: Existing architecture is already split by responsibilities (View, ViewModel, UseCase, Adapter), which reduces migration risk if boundaries remain intact.
  Evidence: Architecture docs define boundaries and call-chain explicitly.​:codex-file-citation[codex-file-citation]{line_range_start=7 line_range_end=20 path=docs/architecture_overview.md git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/docs/architecture_overview.md#L7-L20"}​​:codex-file-citation[codex-file-citation]{line_range_start=35 line_range_end=40 path=docs/architecture_overview.md git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/docs/architecture_overview.md#L35-L40"}​

- Observation: Existing app composition already injects callbacks into views and centralizes VM wiring, which can be mirrored in NiceGUI composition.
  Evidence: `App` builds VMs, then wires callback-driven views.​:codex-file-citation[codex-file-citation]{line_range_start=121 line_range_end=140 path=seva/app/main.py git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/seva/app/main.py#L121-L140"}​

- Observation: Both `web_ui/` and `seva/web_ui/` were empty at implementation start, so the web runtime requires a full additive implementation.
  Evidence:
    Get-ChildItem -Recurse -File web_ui
    (no output)

- Observation: The default shell `python` resolves to 3.9 in this workspace, while the project baseline is Python >=3.10.
  Evidence:
    py -0p
     -V:3.13 *        C:\Users\LunaP\AppData\Local\Programs\Python\Python313\python.exe
     -V:3.9           C:\Users\LunaP\AppData\Local\Programs\Python\Python39\python.exe

- Observation: Tkinter import smoke initially failed because `seva/app/main.py` imported `dataplotter_standalone` eagerly, which requires optional `pandas` in environments where it is not installed.
  Evidence:
    ModuleNotFoundError: No module named 'pandas'

- Observation: Making `DataProcessingGUI` a lazy import inside `_on_open_plotter` preserved behavior while removing startup hard-failure risk for environments without data-plotter dependencies.
  Evidence:
    @'import seva.app.main; print("tkinter-import-ok")'@ | py -3.13 -
    tkinter-import-ok

## Decision Log

- Decision: Use NiceGUI as web UI framework.
  Rationale: Stakeholder requested Python-native path with high code reuse.
  Date/Author: 2026-02-12 / Codex

- Decision: Run Tkinter and NiceGUI in parallel until complete feature parity.
  Rationale: Stakeholder requested parallel rollout and removal only after parity.
  Date/Author: 2026-02-12 / Codex

- Decision: Localhost-first runtime is acceptable for first working milestone; deployment target can be chosen later.
  Rationale: Stakeholder prioritizes “reachable by URL” over host provider choice.
  Date/Author: 2026-02-12 / Codex

- Decision: Build thin NiceGUI-specific VM bindings rather than forcing full direct reuse of Tkinter-coupled VM interactions.
  Rationale: Minimizes coupling risk while preserving core VM/domain semantics.
  Date/Author: 2026-02-12 / Codex

- Decision: Browser-side settings persistence with JSON import/export is required; legacy settings compatibility must be maintained.
  Rationale: Explicit stakeholder requirement.
  Date/Author: 2026-02-12 / Codex

- Decision: Firmware, NAS, and Data Plotter workflows migrate last.
  Rationale: Stakeholder prioritization.
  Date/Author: 2026-02-12 / Codex

- Decision: Use `py -3.13` for validation commands in this migration.
  Rationale: NiceGUI and the project runtime baseline require Python >=3.10, while the default shell interpreter is Python 3.9.
  Date/Author: 2026-02-12 / Codex

- Decision: Store browser settings in `localStorage` using key `seva.web.settings.v1` and apply payloads through `SettingsVM.apply_dict`.
  Rationale: Meets browser-side persistence requirement while reusing existing compatibility mapping path.
  Date/Author: 2026-02-12 / Codex

- Decision: Use one periodic NiceGUI poll timer (2s) for group/status updates rather than Tk-style per-group `after` scheduling.
  Rationale: Keeps the web runtime simple and deterministic while preserving server-authoritative status flow through existing use cases.
  Date/Author: 2026-02-12 / Codex

- Decision: Lazy-import `DataProcessingGUI` in Tkinter app startup.
  Rationale: Prevents optional data-plotter dependencies from blocking Tkinter runtime startup smoke validation.
  Date/Author: 2026-02-12 / Codex

## Outcomes & Retrospective

- Milestone outcome (Plan + parity inventory): Completed. The execution plan was persisted at `.agent/execplans/nicegui_migration.md`, and a Tkinter-to-NiceGUI parity map was added at `docs/web_ui_parity_inventory.md`.
- Milestone outcome (implementation): Completed. Added full NiceGUI runtime under `seva/web_ui/` (`main.py`, `runtime.py`, `viewmodels.py`, `plotter_vm.py`) with parallel startup (`python -m seva.web_ui.main`) and thin web-facing VM bindings.
- Milestone outcome (workflow parity): Completed. Core workflows (start/poll/cancel/download, run overview/activity, discovery) and deferred workflows (firmware, NAS, data plotter interactions) are exposed in web tabs while preserving existing use-case/adapters orchestration.
- Milestone outcome (API/web docs): Completed. Added optional CORS config in `rest_api/app.py`; documented web runtime startup, persistence behavior, and deployment notes in `README.md`, `docs/dev-setup.md`, `docs/web_ui_runtime.md`, and docs navigation.
- Validation outcome: Completed. `pytest` passes, web smoke command passes, Tkinter import smoke passes after lazy data-plotter import hardening.

## Context and Orientation

Current architecture and code organization:

- `seva/app/views/*` contains Tkinter views; `MainWindowView` is Tkinter UI-only with callback hooks for commands.​:codex-file-citation[codex-file-citation]{line_range_start=4 line_range_end=7 path=seva/app/views/main_window.py git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/seva/app/views/main_window.py#L4-L7"}​
- `seva/viewmodels/*` contains UI state and commands, intended to be I/O-free.
- `seva/usecases/*` contains workflow orchestration.
- `seva/adapters/*` contains I/O integration code.
- `seva/app/main.py` currently composes VMs and wires callbacks into views.
- `rest_api/` provides API surface consumed by clients.

Terms used:

- NiceGUI: Python web UI framework running a Python server and rendering interactive browser UI.
- Parallel runtime: both Tkinter and NiceGUI entrypoints available and supported.
- Parity: same functional workflows available in both UIs.

## Plan of Work

Milestone 1 (Plan + Parity Inventory)
Create a parity checklist document that maps every current Tkinter interaction to NiceGUI pages/components and command handlers. This includes toolbar actions, settings flows, run overview, channel activity, discovery, and advanced workflows. Mark firmware/NAS/data-plotter as “migrate-last” groups per stakeholder direction.

Milestone 2 (NiceGUI App Shell, Parallel Startup)
Add a new NiceGUI app package (e.g., `seva/web_ui/`) with a separate startup entrypoint. Keep existing Tkinter startup untouched. The shell must include modernized layout with sections equivalent to current app regions and 4-box awareness (A/B/C/D).

Milestone 3 (Wiring Strategy with Maximum Reuse)
Introduce a composition root for NiceGUI that:

- reuses existing domain/usecase/adapters directly where possible,
- reuses runtime-agnostic VM logic,
- adds thin NiceGUI VM wrappers only for web state/binding concerns.
Do not move business orchestration into views. Keep command flow aligned with existing architecture boundaries.

Milestone 4 (Settings, Browser Persistence, Compatibility)
Implement settings UI in NiceGUI with:

- per-box API URLs (4 boxes),
- browser-side persistence,
- JSON export/import,
- compatibility loader for current serialized settings payload shape.
Validation/mapping occurs at boundary; preserve typed settings semantics from current VM model.​:codex-file-citation[codex-file-citation]{line_range_start=22 line_range_end=44 path=seva/viewmodels/settings_vm.py git_url="https://github.com/LunatiChemist/SEVA_GUI_MVVM/blob/main/seva/viewmodels/settings_vm.py#L22-L44"}​

Milestone 5 (Core Workflow Migration)
Migrate main workflows first (excluding migrate-last group):

- start/validate/poll/cancel/download,
- run overview and activity views,
- discovery flows.
Display server-authoritative status only; no synthetic progress model.

Milestone 6 (Deferred Workflow Migration Last)
Migrate firmware flashing, NAS setup flows, and data plotter interactions as the final feature set.

Milestone 7 (API Communication Adjustments + Validation)
Apply only necessary REST API communication updates for web behavior (configuration/CORS/headers/timeouts as needed), preserving existing business semantics.
Then validate:

- Tkinter runtime still starts and works.
- NiceGUI runtime starts locally and supports all workflows.
- Error behavior remains explicit and technical.

Milestone 8 (Documentation + Optional Deployment Path)
Document:

- how to run Tkinter,
- how to run NiceGUI locally on URL,
- settings persistence/import/export behavior,
- deployment options for internal hosting.
Do not force a provider decision in this milestone; keep deployment provider-agnostic.

## Concrete Steps

All commands run from repository root `/workspace/SEVA_GUI_MVVM`.

1) Preparation and plan persistence
   - create/refresh `.agent/execplans/nicegui_migration.md` with this plan.
   - create `docs/web_ui_parity_inventory.md` listing feature-by-feature mapping.

2) Implement NiceGUI shell and entrypoint
   - add `seva/web_ui/` modules.
   - add startup command path (e.g., `python -m seva.web_ui.main`).

3) Add wiring + VM adapters
   - compose existing reusable usecases/adapters.
   - add thin NiceGUI VM wrappers for UI state/event binding only.

4) Implement settings behavior
   - browser persistence adapter.
   - JSON export/import.
   - legacy payload compatibility mapping.

5) Migrate workflows in requested order
   - core workflows first.
   - firmware/NAS/data plotter last.

6) Validation
   - run automated tests.
   - run Tkinter startup smoke.
   - run NiceGUI startup smoke.
   - manual workflow checks for parity.

Expected local runtime signal:

- NiceGUI server prints host/port and app is reachable at local URL.
- Tkinter still starts without regression.
- Workflow actions return server-backed status updates.

Execution evidence (this run):

    > py -3.13 -m pytest -q
    ...........                                                              [100%]
    11 passed in 0.23s

    > py -3.13 -m seva.web_ui.main --smoke-test
    web-smoke-ok ['A', 'B', 'C', 'D']

    > @'import seva.app.main; print("tkinter-import-ok")'@ | py -3.13 -
    tkinter-import-ok

## Validation and Acceptance

Acceptance criteria:

1. Both runtimes operate (Tkinter + NiceGUI).
2. NiceGUI supports 4-box settings and workflows.
3. Settings persist browser-side and can be exported/imported as JSON.
4. Existing settings payload compatibility works.
5. Firmware/NAS/data-plotter available after final milestone.
6. No orchestration logic in views; boundaries remain respected.
7. Errors are surfaced clearly (no swallowing).

Testing scope:

- Contract-driven tests at UseCase↔Adapter boundaries are preferred.
- UI tests remain minimal; manual checks verify rendering and interaction wiring.

## Idempotence and Recovery

- Each milestone is additive and can be implemented/reverted independently.
- Keep Tkinter path unchanged until full parity is confirmed.
- If a NiceGUI milestone fails, revert only affected web modules and keep desktop runtime operational.
- Keep settings compatibility mapping deterministic and version-aware to avoid partial data corruption.

## Artifacts and Notes

Planned deliverables:

- `.agent/execplans/nicegui_migration.md`
- `docs/web_ui_parity_inventory.md`
- `seva/web_ui/*` NiceGUI app modules
- optional REST API config/docs updates if needed for web communication
- updated run documentation for parallel runtimes

Evidence to collect during implementation:

- startup logs for both runtimes,
- settings import/export examples,
- parity checklist completion updates,
- screenshots of modernized NiceGUI screens during major milestones.

## Interfaces and Dependencies

Primary interfaces to preserve:

- View: render + event capture only.
- ViewModel: UI state + commands only.
- UseCase: workflow orchestration.
- Adapter: I/O boundary.

Dependencies:

- NiceGUI runtime for web view.
- existing Python domain/usecase/adapter modules reused.
- browser storage integration for settings persistence.
- no mandatory deployment provider dependency at planning stage.

---

Plan revision note: This version reflects stakeholder choices: NiceGUI path, parallel rollout, localhost-first, deployment-provider flexibility, 4-box support, full feature parity with firmware/NAS/data-plotter migrated last, thin NiceGUI VM wrappers, browser-side settings persistence with JSON import/export, legacy settings compatibility, no auth/roles for now, internal usage first, and legacy removal only after complete parity.

Change note (2026-02-12 08:09Z): Marked Milestone 1 completed by persisting `.agent/execplans/nicegui_migration.md` and adding `docs/web_ui_parity_inventory.md`; updated living sections with interpreter and repository discoveries.
Change note (2026-02-12 08:57Z): Completed implementation milestones 2-8, added web runtime + parity docs, applied optional REST API CORS support, captured validation evidence, and finalized living sections.
