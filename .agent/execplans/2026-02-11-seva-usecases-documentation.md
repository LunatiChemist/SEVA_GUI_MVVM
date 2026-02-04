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

- [x] (2026-02-04 00:42Z) Map all usecases to the UI commands and adapters they call.
- [x] (2026-02-04 00:44Z) Add/expand module docstrings for each usecase file.
- [x] (2026-02-04 00:48Z) Add/expand class/function docstrings with call-chain and error cases.
- [x] (2026-02-04 00:49Z) Add inline comments for complex orchestration logic.
- [x] (2026-02-04 00:52Z) Update `docs/workflows_seva.md` with detailed workflows and Mermaid diagrams.
- [x] (2026-02-04 00:54Z) Final consistency pass for Google style and completeness, including validation evidence.
- [x] (2026-02-04 01:32Z) Post-stabilization revalidation completed (`pytest -q` and usecase docstring audit) with fresh evidence captured.

## Surprises & Discoveries

- Observation: `seva/usecases` includes significantly more modules than the initial non-exhaustive context list (21 Python modules).
  Evidence: Repository file scan with `rg --files seva/usecases`.
- Observation: Many callable methods already had short docstrings but lacked the detailed orchestration context required by this plan.
  Evidence: AST audit initially reported missing method docstrings across planning, discovery, polling, layout, and diagnostics usecases.
- Observation: Post-stabilization verification remained green without additional source edits.
  Evidence: `pytest -q` returned `8 passed in 0.30s` and the usecase AST audit returned `OK`.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/usecases`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent
- Decision: Keep implementation changes documentation-only and avoid behavior refactors, except adding explicit exception chaining (`from exc`) where already mapping errors.
  Rationale: The task scope is usecase documentation and workflow mapping; behavior changes would increase risk without requirement.
  Date/Author: 2026-02-04 / Agent
- Decision: Expand `docs/workflows_seva.md` into an explicit entrypoint-to-usecase map plus Mermaid sequence diagrams.
  Rationale: This makes upstream UI triggers and downstream adapter calls traceable for novice onboarding.
  Date/Author: 2026-02-04 / Agent

## Outcomes & Retrospective

- Outcome: Completed full pass on `seva/usecases` doc coverage (module/class/function/method), added targeted orchestration comments, and rewrote workflow documentation with end-to-end call chains.
- Outcome: Validation succeeded (`pytest -q` all green), and an AST docstring audit confirms complete docstring coverage for `seva/usecases/*.py`.
- Outcome: Post-stabilization rerun reconfirmed acceptance criteria (`OK` audit + `8 passed in 0.30s`).
- Remaining gaps: None for this ExecPlan scope.
- Lesson learned: A small scripted docstring audit is effective as a fast acceptance check for documentation refactors across many files.

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

All steps are run from the repository root (`c:\Users\LunaP\OneDrive - UBC\Dokumente\Chemistry\Potentiostats\GUI Testing\SEVA_GUI_MVVM`).

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

4) Validation:

    pytest -q

5) Documentation completeness check:

    @'
    import ast
    from pathlib import Path
    missing = []
    for p in sorted(Path("seva/usecases").glob("*.py")):
        mod = ast.parse(p.read_text(encoding="utf-8"))
        if not ast.get_docstring(mod):
            missing.append(f"{p}: module")
        for node in mod.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not ast.get_docstring(node):
                missing.append(f"{p}: {node.name}")
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(sub):
                        missing.append(f"{p}: {node.name}.{sub.name}")
    print("OK" if not missing else "\n".join(missing))
    '@ | python -

## Validation and Acceptance

- All usecase files have Google-style module docstrings with call contexts.
- All classes/functions have Google-style docstrings with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex orchestration steps.
- `docs/workflows_seva.md` describes all major workflows and participating usecases.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert and reapply documentation-only changes with `git restore <file>` as needed.

## Artifacts and Notes

Delivered artifacts:

- Updated docstrings and inline comments in `seva/usecases/*.py`.
- Updated `docs/workflows_seva.md` with workflow descriptions.

Validation evidence snippets:

    > pytest -q
    ........                                                                 [100%]
    8 passed in 0.26s

    > python <docstring audit script>
    OK: docstrings present for all modules/classes/functions/methods in seva/usecases/*.py

Post-stabilization evidence snippets:

    > pytest -q
    ........                                                                 [100%]
    8 passed in 0.30s

    > python <docstring audit script>
    OK

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- Ports in `seva/domain/ports.py`
- Adapters in `seva/adapters/*`

---

Change note (2026-02-04): Updated living sections to completed state, recorded discoveries/decisions, added concrete validation steps, and embedded short validation evidence transcripts.
Change note (2026-02-04 01:32Z): Added post-stabilization validation checkpoint and fresh evidence snippets.
