# Document seva/viewmodels in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

ViewModels are the UI state and command layer. This plan documents each viewmodel so a new developer can understand what UI state it owns, which commands it exposes, and how it interacts with usecases. The documentation must keep ViewModels free of IO and business logic, aligning with MVVM boundaries.

Success is observable when:

- Every file in `seva/viewmodels` starts with a Google-style module docstring describing purpose, dependencies, and call contexts.
- Every class/function has a Google-style docstring with summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments explain complex state transitions or UI command flows.
- `docs/classes_seva.md` and `docs/workflows_seva.md` describe viewmodel responsibilities and their usecase dependencies.

## Progress

- [ ] (2026-02-11 00:00Z) Map viewmodels to UI views and usecase dependencies.
- [ ] (2026-02-11 00:00Z) Add/expand module docstrings for each viewmodel file.
- [ ] (2026-02-11 00:00Z) Add/expand class/function docstrings with call-chain and error cases.
- [ ] (2026-02-11 00:00Z) Add inline comments for complex UI state logic.
- [ ] (2026-02-11 00:00Z) Update `docs/classes_seva.md` and `docs/workflows_seva.md` with viewmodel roles.
- [ ] (2026-02-11 00:00Z) Final consistency pass for Google style and completeness.

## Surprises & Discoveries

- Observation: None yet.
  Evidence: Plan initialization only.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/viewmodels`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent

## Outcomes & Retrospective

- Status: Not started. This section will be updated after milestones and completion.

## Context and Orientation

ViewModels coordinate UI state and commands. They should not perform IO or build API payloads. Instead, they invoke usecases or adapters via injected dependencies. Documenting these files clarifies which UI elements are bound to which state variables and which commands trigger workflows.

Key files (non-exhaustive):

- `seva/viewmodels/experiment_vm.py`
- `seva/viewmodels/plate_vm.py`
- `seva/viewmodels/progress_vm.py`
- `seva/viewmodels/runs_vm.py`
- `seva/viewmodels/settings_vm.py`
- `seva/viewmodels/live_data_vm.py`

## Plan of Work

1) Map each viewmodel to its UI views and usecases.
   - Identify which views bind to each viewmodel and which usecases they trigger.
   - Capture these relationships in `docs/classes_seva.md` and `docs/workflows_seva.md`.

2) Add module docstrings for each viewmodel file.
   - Explain UI state responsibilities, dependencies, and typical call contexts.

3) Add/expand class/function docstrings.
   - Include summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
   - Explicitly mention which usecases are invoked and why.

4) Add inline comments for complex state updates.
   - Focus on derived state or multi-step UI updates.

5) Update documentation files.
   - Ensure viewmodel responsibilities and their relationships to views/usecases are described.

6) Final pass for consistency.

## Concrete Steps

All steps are run from the repository root (`/workspace/SEVA_GUI_MVVM`).

1) Inspect viewmodel files:

    sed -n '1,200p' seva/viewmodels/experiment_vm.py
    sed -n '1,200p' seva/viewmodels/plate_vm.py
    sed -n '1,200p' seva/viewmodels/progress_vm.py
    sed -n '1,200p' seva/viewmodels/runs_vm.py
    sed -n '1,200p' seva/viewmodels/settings_vm.py
    sed -n '1,200p' seva/viewmodels/live_data_vm.py
    sed -n '1,200p' seva/viewmodels/status_format.py

2) Add/expand docstrings and inline comments in each file.

3) Update `docs/classes_seva.md` and `docs/workflows_seva.md`.

4) Optional validation (documentation only):

    pytest -q

## Validation and Acceptance

- All viewmodel files have Google-style module docstrings with call contexts.
- All classes/functions have Google-style docstrings with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex UI state logic.
- `docs/classes_seva.md` and `docs/workflows_seva.md` describe viewmodel responsibilities.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert and reapply documentation-only changes with `git restore <file>` as needed.

## Artifacts and Notes

Expected artifacts:

- Updated docstrings and inline comments in `seva/viewmodels/*.py`.
- Updated `docs/classes_seva.md` and `docs/workflows_seva.md` sections for viewmodels.

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- Usecases in `seva/usecases/*`
- Views in `seva/app/views/*`

---

Change note: Initial plan created to cover the viewmodel subsystem in deep detail.
