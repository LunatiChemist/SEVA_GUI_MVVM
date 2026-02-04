# Document seva/app and seva/app/views in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

The `seva/app` layer contains application entrypoints, controllers, and Tkinter view code. This plan documents every file in `seva/app` and `seva/app/views` so a new developer can understand how UI elements are assembled, how they bind to viewmodels, and how user actions trigger usecases through viewmodels.

Success is observable when:

- Every file in `seva/app` and `seva/app/views` starts with a Google-style module docstring describing purpose, dependencies, and call contexts.
- Every class/function has a Google-style docstring with summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments explain complex UI layout, event binding, or rendering logic.
- `docs/workflows_seva.md` documents UI entrypoints and their workflow handoffs.

## Progress

- [x] (2026-02-04 18:15Z) Mapped UI entrypoints and controller flows to viewmodels/usecases by tracing `seva/app/main.py`, `seva/app/run_flow_presenter.py`, and controller callbacks.
- [x] (2026-02-04 01:09Z) Added/expanded module docstrings across all files in `seva/app` and `seva/app/views`, including ancillary controller/utility modules.
- [x] (2026-02-04 01:09Z) Added/expanded class/function docstrings with parameter-focused Google-style sections across app/view classes and helper functions.
- [x] (2026-02-04 01:09Z) Added inline comments and explanatory docstrings for complex UI/event sections (selection behavior, nested Tk callbacks, layout-sensitive helpers).
- [x] (2026-02-04 18:19Z) Updated `docs/workflows_seva.md` with UI entrypoints and view-model/usecase handoffs.
- [x] (2026-02-04 01:09Z) Final consistency pass completed (AST docstring check + compile + test run).
- [x] (2026-02-04 01:33Z) Post-stabilization revalidation completed (`app-docstring-check`, `python -m compileall -q seva/app`, `pytest -q`).

## Surprises & Discoveries

- Observation: The app wiring fans out across toolbar callbacks, per-panel callbacks, and settings-dialog callbacks; documenting by event source is clearer than documenting per class.
  Evidence: New `UI Entrypoints and Handoffs` section in `docs/workflows_seva.md` groups actions by user trigger.
- Observation: `RunOverviewView` wired a "Copy" button to `_copy_to_clipboard`, but the helper did not exist.
  Evidence: Added `_copy_to_clipboard()` in `seva/app/views/run_overview_view.py` to match existing button command.
- Observation: `dataplotter_standalone.py` had mixed legacy comments/docstrings and required careful cleanup to avoid syntax regressions while adding Google-style content.
  Evidence: `python -m compileall -q seva/app` succeeds after docstring normalization.
- Observation: Post-stabilization checks confirmed app/view documentation coverage and runtime safety remained intact.
  Evidence: `app-docstring-check: OK`, compileall exited without output, and `pytest -q` returned `8 passed in 0.12s`.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/app` and `seva/app/views`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent
- Decision: Prioritize entrypoint-facing and public API docstrings first, then sweep helper methods.
  Rationale: This delivers usable onboarding value quickly while keeping the plan incremental and testable.
  Date/Author: 2026-02-04 / Agent
- Decision: Use an AST-based docstring audit as final gate for function/method coverage.
  Rationale: It gives deterministic evidence that documentation expectations are met across all `seva/app` modules.
  Date/Author: 2026-02-04 / Agent

## Outcomes & Retrospective

- Milestone update (2026-02-04): UI entrypoint mapping is now documented in `docs/workflows_seva.md`; remaining work is docstring/comment normalization in `seva/app` and `seva/app/views`.
- Milestone update (2026-02-04): Expanded docstrings in controllers/presenter and major views; test suite remains green after changes.
- Completion update (2026-02-04): Completed documentation sweep for `seva/app` + `seva/app/views`, including helper functions and nested Tk callbacks; validation checks pass.
- Revalidation update (2026-02-04 01:33Z): Post-stabilization checks remained green with no additional source edits.

## Context and Orientation

The app layer includes the main entrypoints, controller objects, and all Tkinter views. Views should remain UI-only and should not perform IO or business logic. Documentation must make this boundary explicit, showing how views bind to viewmodels and how commands are routed into usecases.

Key files (non-exhaustive):

- `seva/app/main.py`
- `seva/app/controller.py`
- `seva/app/run_flow_presenter.py`
- `seva/app/polling_scheduler.py`
- `seva/app/views/main_window.py`
- `seva/app/views/experiment_panel_view.py`
- `seva/app/views/run_overview_view.py`
- `seva/app/views/well_grid_view.py`
- `seva/app/views/settings_dialog.py`
- `seva/app/views/channel_activity_view.py`

## Plan of Work

1) Map UI entrypoints and controller flows.
   - Identify how `main.py` initializes the application and wires viewmodels.
   - Identify how controllers and presenters connect UI events to viewmodel commands.
   - Record these relationships in `docs/workflows_seva.md`.

2) Add module docstrings for each file.
   - Include purpose, UI responsibilities, dependencies, and typical call contexts.
   - Emphasize that views are UI-only and do not implement business logic.

3) Add/expand class/function docstrings.
   - Include summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
   - Document event handlers and their connections to viewmodel commands.

4) Add inline comments for complex UI layout or behavior.
   - Focus on sections that would be hard for new developers to read.

5) Update `docs/workflows_seva.md`.
   - Add a UI entrypoint section that maps view events to viewmodels and usecases.

6) Final consistency pass.

## Concrete Steps

All steps are run from the repository root (`SEVA_GUI_MVVM`).

1) Inspect app and view files:

    sed -n '1,200p' seva/app/main.py
    sed -n '1,200p' seva/app/controller.py
    sed -n '1,200p' seva/app/run_flow_presenter.py
    sed -n '1,200p' seva/app/polling_scheduler.py
    sed -n '1,200p' seva/app/views/main_window.py
    sed -n '1,200p' seva/app/views/experiment_panel_view.py
    sed -n '1,200p' seva/app/views/run_overview_view.py
    sed -n '1,200p' seva/app/views/well_grid_view.py
    sed -n '1,200p' seva/app/views/settings_dialog.py
    sed -n '1,200p' seva/app/views/channel_activity_view.py

2) Add/expand docstrings and inline comments in each file.

3) Update `docs/workflows_seva.md` with UI entrypoints and bindings.

4) Optional validation (documentation only):

    pytest -q

Validation evidence:

    OK: all function/method docstrings include Args where parameters exist.

    python -m compileall -q seva/app
    # (no output, success)

    ........                                                                 [100%]
    8 passed in 0.16s

Post-stabilization evidence:

    app-docstring-check: OK

    python -m compileall -q seva/app
    # (no output, success)

    ........                                                                 [100%]
    8 passed in 0.12s

## Validation and Acceptance

- All app and view files have Google-style module docstrings with call contexts.
- All classes/functions have Google-style docstrings with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex UI layout and event handling.
- `docs/workflows_seva.md` describes UI entrypoints and viewmodel/usecase connections.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert and reapply documentation-only changes with `git restore <file>` as needed.

## Artifacts and Notes

Expected artifacts:

- Updated docstrings and inline comments in `seva/app/*.py` and `seva/app/views/*.py`.
- Updated `docs/workflows_seva.md` with UI entrypoint documentation.

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- ViewModels in `seva/viewmodels/*`
- Usecases in `seva/usecases/*`

---

Change note (2026-02-04): Completed full app/views documentation sweep, added AST-based docstring validation evidence, and finalized plan milestones.
Change note (2026-02-04 01:33Z): Added post-stabilization revalidation milestone and evidence snippets.
