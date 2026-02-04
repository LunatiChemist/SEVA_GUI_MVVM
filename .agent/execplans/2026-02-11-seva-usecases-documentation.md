# Document seva/usecases in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

Usecases orchestrate GUI workflows. This plan documents each usecase so a new developer can understand how user actions flow through the system, which adapters they call, and how domain objects are constructed and validated. The documentation must clearly tie each usecase to its upstream viewmodels and downstream adapters, and it must highlight error handling and server-authoritative status use.

Success is observable when:

- Every file in `seva/usecases` starts with a Google-style module docstring describing purpose, dependencies, and call contexts.
- Every class/function has a Google-style docstring with summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments explain complex orchestration steps or branching logic.
- `docs/workflows_seva.md` contains a detailed workflow map covering each usecase.

## Progress

- [ ] (2026-02-11 00:00Z) Map all usecases to the UI commands and adapters they call.
- [ ] (2026-02-11 00:00Z) Add/expand module docstrings for each usecase file.
- [ ] (2026-02-11 00:00Z) Add/expand class/function docstrings with call-chain and error cases.
- [ ] (2026-02-11 00:00Z) Add inline comments for complex orchestration logic.
- [ ] (2026-02-11 00:00Z) Update `docs/workflows_seva.md` with detailed workflows.
- [ ] (2026-02-11 00:00Z) Final consistency pass for Google style and completeness.

## Surprises & Discoveries

- Observation: None yet.
  Evidence: Plan initialization only.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/usecases`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent

## Outcomes & Retrospective

- Status: Not started. This section will be updated after milestones and completion.

## Context and Orientation

Usecases are the orchestration layer. They should not perform IO directly but call adapter ports, build domain objects, and manage workflow sequencing (start, validate, poll, cancel, download, discovery, etc.). These files are the primary bridge between viewmodel commands and adapter calls.

Key files (non-exhaustive):

- `seva/usecases/start_experiment_batch.py`
- `seva/usecases/poll_group_status.py`
- `seva/usecases/download_group_results.py`
- `seva/usecases/cancel_group.py`
- `seva/usecases/cancel_runs.py`
- `seva/usecases/test_connection.py`
- `seva/usecases/discover_devices.py`
- `seva/usecases/run_flow_coordinator.py`

## Plan of Work

1) Map each usecase to UI triggers and adapter dependencies.
   - Identify which viewmodel methods or UI commands call each usecase.
   - Identify which adapters are used and which domain objects are constructed.
   - Capture these relationships in `docs/workflows_seva.md`.

2) Add module docstrings for each usecase file.
   - Document purpose, typical call-chain, and orchestration responsibilities.
   - Include references to adapters and domain types used.

3) Add/expand class/function docstrings.
   - Include summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
   - Document error mapping and the rule that server status is authoritative.

4) Add inline comments for complex orchestration.
   - Emphasize sequencing steps, branching decisions, and error mapping.

5) Update `docs/workflows_seva.md`.
   - Provide detailed, step-by-step flows for start, poll, download, cancel, discovery, and test connection.
   - Include Mermaid sequence diagrams to show GUI → viewmodel → usecase → adapter → REST API calls.

6) Final pass for consistency.

## Concrete Steps

All steps are run from the repository root (`/workspace/SEVA_GUI_MVVM`).

1) Inspect usecase files:

    sed -n '1,200p' seva/usecases/start_experiment_batch.py
    sed -n '1,200p' seva/usecases/poll_group_status.py
    sed -n '1,200p' seva/usecases/download_group_results.py
    sed -n '1,200p' seva/usecases/cancel_group.py
    sed -n '1,200p' seva/usecases/cancel_runs.py
    sed -n '1,200p' seva/usecases/test_connection.py
    sed -n '1,200p' seva/usecases/discover_devices.py
    sed -n '1,200p' seva/usecases/run_flow_coordinator.py

2) Add/expand docstrings and inline comments in each file.

3) Update `docs/workflows_seva.md` with workflows and diagrams.

4) Optional validation (documentation only):

    pytest -q

## Validation and Acceptance

- All usecase files have Google-style module docstrings with call contexts.
- All classes/functions have Google-style docstrings with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex orchestration steps.
- `docs/workflows_seva.md` describes all major workflows and participating usecases.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert and reapply documentation-only changes with `git restore <file>` as needed.

## Artifacts and Notes

Expected artifacts:

- Updated docstrings and inline comments in `seva/usecases/*.py`.
- Updated `docs/workflows_seva.md` with workflow descriptions.

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- Ports in `seva/domain/ports.py`
- Adapters in `seva/adapters/*`

---

Change note: Initial plan created to cover the usecase subsystem in deep detail.
