# Simplify app orchestration and downstream flow around main.py

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows the requirements in `/.agent/PLANS.md` from the repository root. Maintain this document accordingly.

## Purpose / Big Picture

The goal is to dramatically reduce the mental load in `seva/app/main.py` by separating UI wiring from orchestration, centralizing mode and storage metadata handling, and relocating business flow into UseCases. After implementation, a novice should be able to trace a user action like “Start experiment” through a short and clear sequence: UI → UseCase → Coordinator → Adapter. Observable improvements include smaller functions, fewer responsibilities in UI code, and consistent error and metadata handling across flows.

Success looks like:
- UI code that is mostly wiring and rendering without deep control flow or data mapping.
- Domain and UseCase layers owning orchestration, error mapping, and metadata normalization.
- Consistent registry entries and downloads that are built from typed metadata objects rather than ad-hoc dictionaries.

## Progress

- [x] (2026-01-27 10:44-08:00) Review and document current responsibilities of `seva/app/main.py`, `seva/usecases/run_flow_coordinator.py`, `seva/viewmodels/experiment_vm.py`, `seva/domain/runs_registry.py`, `seva/usecases/discover_devices.py`, `seva/usecases/start_experiment_batch.py`, and `seva/usecases/download_group_results.py`.
- [x] (2026-01-27 10:44-08:00) Define target module boundaries and new or updated domain/usecase interfaces (Mode Registry, Storage Meta DTO, Run Flow UseCase, Discovery Assignment UseCase).
- [ ] (2026-01-27 10:44-08:00) Implement refactors and new modules with tests and update all call sites.
- [ ] (2026-01-27 10:44-08:00) Remove legacy paths and validate end-to-end behavior.

## Surprises & Discoveries

- Observation: None yet.
  Evidence: Plan created before implementation.

## Decision Log

- Decision: Treat UI (`seva/app/main.py`) as wiring only, moving orchestration into UseCases and Coordinators.
  Rationale: Align with MVVM + Hexagonal guardrails and reduce mental load.
  Date/Author: 2026-01-27 / Codex

## Outcomes & Retrospective

- (2026-01-27 10:44-08:00) Milestone 1 complete: added stub modules with docstrings for run flow presenter, polling scheduler, settings/discovery/download controllers, StorageMeta, BuildStorageMeta, BuildExperimentPlan, ModeRegistry, and DiscoverAndAssignDevices without changing runtime wiring.

## Context and Orientation

This repository is a desktop UI application organized around MVVM and Hexagonal Architecture. Terms used in this plan:
- View: UI rendering components. They should not perform I/O or domain mapping.
- ViewModel: UI state and commands. It should not perform network or filesystem I/O and should not build API payloads.
- UseCase: Application orchestration and business flow (start/poll/cancel/download, discovery, etc.).
- Adapter: Implementation of ports for external I/O (HTTP, filesystem, devices).
- Coordinator: A flow orchestrator that sequences UseCase calls and tracks run state.
- Registry: Persistent index of run groups used for re-attachment on startup.
- Storage metadata: The set of fields used to build download output paths (experiment name, subdir, client datetime, results dir).

Relevant files (repository-relative paths):
- `seva/app/main.py`: Large UI bootstrap and orchestration logic that needs simplification.
- `seva/app/controller.py`: Adapter/UseCase wiring with current settings.
- `seva/usecases/run_flow_coordinator.py`: Run flow coordinator with polling and download orchestration.
- `seva/viewmodels/experiment_vm.py`: ViewModel currently building domain plans and mode config.
- `seva/domain/runs_registry.py`: Registry storing run metadata as dictionaries.
- `seva/usecases/discover_devices.py`: Discovery logic currently thin; orchestration in UI.
- `seva/usecases/start_experiment_batch.py`: Start use case with a result type that is partially unused.
- `seva/usecases/download_group_results.py`: Download use case validating storage metadata.

This plan must also obey the repo guardrails in `AGENTS.md`: no UI I/O, use domain objects above adapters, centralized mode registry, unified errors, and deletion of legacy paths (no fallbacks).

## Plan of Work

This plan is organized to implement every proposal from sections (1) and (2) of the earlier review, without adding temporary fallback paths. Each section below describes the concrete edits and how to validate them.

1) Split `seva/app/main.py` into focused controllers:
- Introduce new modules such as `seva/app/run_flow_presenter.py`, `seva/app/polling_scheduler.py`, `seva/app/settings_controller.py`, `seva/app/discovery_controller.py`, and `seva/app/download_controller.py`.
- Move logic from `_on_submit`, `_on_cancel_group`, `_on_end_selection`, `_on_download_group_results`, `_on_open_settings`, `_on_discover_devices`, and polling helpers into these controllers.
- Keep `App` in `main.py` as wiring only: it should instantiate controllers and forward events.

2) Centralize Storage Meta creation in a typed domain object:
- Add a `StorageMeta` dataclass in `seva/domain` (e.g., `seva/domain/storage_meta.py`) with explicit fields: experiment, subdir, client_datetime, results_dir.
- Provide a `StorageMetaBuilder` UseCase or domain function (e.g., `seva/usecases/build_storage_meta.py`) that constructs and validates this object from settings and plan meta.
- Update `RunFlowCoordinator` and download flows to use the typed object, and update `RunsRegistry` to store a serialized form of it.
- Remove any UI-side manual construction of storage metadata.

3) Move domain plan building out of `ExperimentVM`:
- Create a `BuildExperimentPlan` UseCase (e.g., `seva/usecases/build_experiment_plan.py`) that consumes a lightweight DTO from the VM (selection + fields + mode selection) and returns `ExperimentPlan` with `WellPlan` instances.
- Adjust `ExperimentVM` to only expose UI state (fields, selection, mode toggles) without creating domain objects.
- Update `App` (or the new controllers) to call the UseCase rather than the VM for plan creation.

4) Create a Mode Registry module:
- Introduce a `ModeRegistry` module (e.g., `seva/domain/modes.py`) that owns mode normalization, clipboard filtering rules, labels, and any mode-specific builders.
- Update `ExperimentVM` to use this registry for copy/paste filtering and parameter grouping.
- Remove direct `_MODE_CONFIG` and `_MODE_BUILDERS` from the VM.

5) Replace UI error mapping with UseCase error mapping:
- Create a consistent error model (e.g., `AppError` or enriched `UseCaseError` with `user_message`).
- Update UseCases and adapters to throw typed errors and map to user-facing messages in the UseCase layer.
- Simplify `_format_error_message` in UI to display the provided user message only.

6) Discovery orchestration in UseCase:
- Create `DiscoverAndAssignDevices` UseCase that takes discovery candidates and the current registry, returns assigned slots, skipped URLs, and a display summary.
- `SettingsDialog` controller should only trigger the UseCase and display results.
- Remove manual assignment and persistence from UI logic.

7) Registry metadata typing:
- Update `RunsRegistry` to store and load typed metadata (PlanMeta DTO and StorageMeta DTO) rather than raw dictionaries.
- Ensure serialization/deserialization is explicit and stable.

8) Simplify start flow result:
- Either populate `started_wells` in `StartBatchResult` or remove the field entirely. Choose one path and delete the legacy path.

## Concrete Steps

All commands assume working directory `/workspace/SEVA_GUI_MVVM`.

1) Read and document the relevant code paths:

    rg --files -g 'main.py' -g 'controller.py' -g 'run_flow_coordinator.py' -g 'experiment_vm.py' -g 'runs_registry.py' -g 'discover_devices.py' -g 'start_experiment_batch.py' -g 'download_group_results.py'

    rg "_on_submit|_on_open_settings|_on_discover_devices|_on_download_group_results|_schedule_poll|_cancel_poll_timer|_stop_polling" seva/app/main.py

    rg "StorageMeta|client_datetime|results_dir" seva -g '*.py'

2) Create new modules and move logic:

    mkdir -p seva/app
    touch seva/app/run_flow_presenter.py seva/app/polling_scheduler.py seva/app/settings_controller.py seva/app/discovery_controller.py seva/app/download_controller.py

3) Update `seva/app/main.py`:
- Replace heavy handlers with thin delegations to the new controllers.
- Ensure UI classes only call controller methods and respond to signals.

4) Implement `StorageMeta` and builder:

    touch seva/domain/storage_meta.py seva/usecases/build_storage_meta.py

5) Implement `BuildExperimentPlan` UseCase:

    touch seva/usecases/build_experiment_plan.py

6) Implement `ModeRegistry`:

    touch seva/domain/modes.py

7) Update UseCases, Registry, and Controllers:
- Update `RunFlowCoordinator` and `DownloadGroupResults` to use typed storage meta.
- Update `RunsRegistry` serialization and persistence.
- Update discovery and settings controllers to use the new `DiscoverAndAssignDevices` UseCase.

8) Remove legacy paths:
- Delete old direct UI metadata construction.
- Delete VM-level mode config and builder definitions.
- Delete unused fields or flows (such as empty `started_wells`, if removed).

9) Add or update tests (UseCase↔Adapter boundary preferred):
- Add tests for `BuildExperimentPlan`, `BuildStorageMeta`, `ModeRegistry`, and `DiscoverAndAssignDevices`.
- Update existing tests for registry load/save if present.

## Milestones

### Milestone 1: Baseline mapping and contracts

Goal: Document current flow and define clear interfaces for new modules (Mode Registry, Storage Meta, Plan Builder, Discovery Assignment). At the end, a novice can read the new module stubs and know the expected inputs/outputs.

Commands:

    rg "class|def" seva/usecases -g '*.py'
    rg "class|def" seva/domain -g '*.py'

Acceptance: New modules exist with docstrings describing inputs/outputs, and no production behavior has changed yet.

Rollback/Recovery: Delete the newly created stub files if the plan is paused before implementation.

### Milestone 2: Extract run-flow orchestration from UI

Goal: Move `_on_submit`, run tracking, and polling logic into a dedicated controller and scheduler, leaving `App` as wiring only. At the end, `main.py` should only instantiate components and register callbacks.

Commands:

    rg "class App" -n seva/app/main.py
    rg "RunFlow" -n seva/app

Acceptance: `main.py` contains only wiring and delegation, and the new controller encapsulates start/stop/poll logic without UI-specific code.

Rollback/Recovery: Revert `main.py` and the new controllers if the event flow becomes unclear or breaks basic launch.

### Milestone 3: Centralized storage metadata and plan building

Goal: Introduce typed `StorageMeta` and `BuildExperimentPlan`, update downstream calls, and delete UI-side construction. At the end, the only way to create a plan or storage metadata is via UseCases.

Commands:

    rg "StorageMeta" -n seva
    rg "build_experiment_plan" -n seva

Acceptance: UI code no longer constructs `ExperimentPlan` or storage dicts; UseCases return typed objects used by coordinator and registry.

Rollback/Recovery: Revert usecase integration commits and restore UI-based plan/meta creation if metadata validation breaks downloads.

### Milestone 4: Mode registry and error handling consolidation

Goal: Move mode logic into `ModeRegistry` and ensure UI does not map API errors to strings. At the end, UI errors are derived from UseCase error messages, and all mode configuration lives in one module.

Commands:

    rg "_MODE_CONFIG|_MODE_BUILDERS" -n seva
    rg "_format_error_message" -n seva/app/main.py

Acceptance: No mode config remains in ViewModels; error mapping is centralized in UseCases.

Rollback/Recovery: Revert ModeRegistry integration if copy/paste of modes fails, then add targeted tests before reattempting.

### Milestone 5: Discovery orchestration in UseCase + registry typing

Goal: Move discovery assignment and persistence logic into UseCase; type registry metadata. At the end, the settings dialog just triggers UseCase calls and renders results.

Commands:

    rg "Discover" -n seva
    rg "RunsRegistry" -n seva/domain/runs_registry.py

Acceptance: Discovery and registry flows use typed DTOs and predictable fields; no UI data mapping remains.

Rollback/Recovery: Revert registry serialization changes if older stored data cannot be loaded; provide a one-time migration or instructions to delete the registry JSON if necessary.

## Validation and Acceptance

Validation must be performed after each milestone and at the end:

1) Run unit tests (or add if missing):

    pytest

Expected: All tests pass; new tests for plan building, storage meta, mode registry, and discovery assignment succeed.

2) Manual smoke check (if UI can be launched in this environment):

    python -m seva.app.main

Expected: App starts, settings dialog opens, and starting/canceling an experiment does not crash.

If UI launch is not possible, use targeted UseCase tests instead and record the limitation.

## Idempotence and Recovery

All steps are designed to be repeatable. If a step fails, revert the last commit and re-apply the step after fixing the issue. Avoid partial migrations: when a new path is introduced, remove the old path in the same change or the next immediately following change, as required by the no-legacy constraint.

If registry metadata changes break existing stored data, provide a documented recovery path:
- Back up `~/.seva/runs_registry.json`.
- Run a one-time migration script (to be added if needed), or delete the file to reset the registry.

## Artifacts and Notes

Examples of expected outputs:

    $ rg "StorageMeta" -n seva
    seva/domain/storage_meta.py:1:class StorageMeta:
    seva/usecases/build_storage_meta.py:1:def build_storage_meta(...)

    $ pytest
    ===================== 10 passed in 2.34s =====================

These transcripts should be updated as the plan is executed.

## Interfaces and Dependencies

New or updated interfaces to implement (names may be adjusted if the repo uses different conventions):
- `seva/domain/storage_meta.py`: `StorageMeta` dataclass with fields: experiment, subdir (optional), client_datetime, results_dir.
- `seva/usecases/build_storage_meta.py`: `BuildStorageMeta` or `build_storage_meta(settings, plan_meta) -> StorageMeta`.
- `seva/usecases/build_experiment_plan.py`: `BuildExperimentPlan(vm_state) -> ExperimentPlan`.
- `seva/domain/modes.py`: `ModeRegistry` with methods to normalize mode names, provide UI labels, and filter fields for copy/paste.
- `seva/usecases/discover_and_assign_devices.py`: `DiscoverAndAssignDevices` use case returning assignments and summary.
- `seva/app/run_flow_presenter.py`: orchestrates starting/stopping run flow and connects to `RunFlowCoordinator`.
- `seva/app/polling_scheduler.py`: owns timer scheduling and session cleanup.

All existing adapters remain as they are; no new external dependencies are required. Any new test utilities should be in the repo’s existing testing stack (likely `pytest`).

---

Plan update note: Initial plan created on 2026-01-27 with placeholders for decisions and no implementation yet.
Plan update note: 2026-01-27 10:44-08:00 - completed milestone 1 stubs and updated Progress/Outcomes to reflect baseline mapping and interface scaffolding.
