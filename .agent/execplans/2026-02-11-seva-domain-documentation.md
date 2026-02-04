# Document seva/domain and seva/domain/params in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

`seva/domain` defines the core domain objects, port interfaces, mode registry, validation helpers, and parameter schemas that the entire GUI relies on. This plan produces exhaustive documentation for these domain files so a new developer can understand the data model, invariants, and how domain types are passed through usecases and adapters.

Success is observable when:

- Every `seva/domain/*.py` and `seva/domain/params/*.py` file begins with a Google-style module docstring that explains purpose, upstream/downstream dependencies, and call contexts.
- Every class and function has a Google-style docstring including summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- `docs/classes_seva.md` contains a detailed description of domain types, relationships, and the mode registry.

## Progress

- [x] (2026-02-04 00:18Z) Mapped domain model usage and verified domain files consumed by usecases/adapters before editing docs.
- [x] (2026-02-04 00:31Z) Expanded module docstrings in targeted domain files with dependency and call-context details (`discovery.py`, `entities.py`, `modes.py`, `storage_meta.py`, `params/ac.py`, `params/cv.py`).
- [x] (2026-02-04 00:34Z) Added missing class/function docstrings across `seva/domain` and `seva/domain/params` (including protocol methods and dataclass helper methods).
- [x] (2026-02-04 00:35Z) Added inline comments for complex normalization/persistence branches in `runs_registry.py` and mode field filtering in `modes.py`.
- [x] (2026-02-04 00:37Z) Updated `docs/classes_seva.md` with domain invariants, call-chain examples, and explicit mode-registry responsibilities.
- [x] (2026-02-04 00:39Z) Ran final consistency and validation pass (`docstring-check` + `pytest -q`) and recorded evidence.

## Surprises & Discoveries

- Observation: The repository already had broad module-level documentation coverage; gaps were concentrated in method-level docstrings (especially dunder/helpers and protocol methods).
  Evidence: Initial AST scan listed missing method docstrings in `entities.py`, `ports.py`, `runs_registry.py`, and params helpers, while module docstrings were already present.
- Observation: A full AST pass after edits confirmed no missing module/class/function docstrings under `seva/domain`.
  Evidence:

    docstring-check: OK (no missing module/class/function docstrings)

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/domain` and `seva/domain/params`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent
- Decision: Prioritize missing/incomplete docstrings and augment existing module docstrings where context was too terse, instead of rewriting already-detailed files.
  Rationale: This preserved prior high-quality documentation while ensuring full coverage and lower risk of regressions in non-documentation code.
  Date/Author: 2026-02-04 / Agent
- Decision: Validate documentation completeness with an AST-based docstring coverage script in addition to test suite execution.
  Rationale: `pytest` validates behavior, while AST validation directly proves the documentation-coverage acceptance criteria.
  Date/Author: 2026-02-04 / Agent

## Outcomes & Retrospective

- Outcome: Completed planned documentation pass for domain modules, method-level APIs, and domain architecture notes.
- Outcome: Added targeted inline comments where mapping/normalization behavior could otherwise be misread during maintenance.
- Validation: `pytest -q` passed with no regressions (`8 passed`), and AST coverage check confirmed no missing module/class/function docstrings.
- Retrospective: The existing documentation baseline was stronger than expected; the highest-value improvements were completeness at method granularity and a clearer domain relationship narrative in `docs/classes_seva.md`.

## Context and Orientation

The domain layer defines:

- Entities and DTOs used throughout the GUI.
- Port interfaces for adapters (e.g., job/device/storage ports).
- Mode registry and parameter schemas for experiments.
- Validation helpers and error types.
- Naming conventions and run identifiers.

These files provide the canonical types; above the adapter boundary, raw JSON should never be passed. Instead, domain types and DTOs are used. Documenting these files clarifies the data flows in usecases and viewmodels.

Key files (non-exhaustive):

- `seva/domain/ports.py`
- `seva/domain/models.py`
- `seva/domain/entities.py`
- `seva/domain/modes.py`
- `seva/domain/params/*.py`
- `seva/domain/errors.py`
- `seva/domain/validation.py`
- `seva/domain/mapping.py`

## Plan of Work

1) Map domain objects and their consumers.
   - Identify each domain type, where it is constructed, and which usecases/adapters expect it.
   - Capture these relationships in `docs/classes_seva.md` as a domain overview.

2) Add module docstrings in every domain file.
   - At the top of each file, add a Google-style docstring that explains purpose, dependencies, and typical usecases.
   - For `params` files, document how parameter schemas map to GUI forms and validation endpoints.

3) Add/expand class and function docstrings.
   - Include summary, parameters, returns, side effects, call-chain, usage scenarios, and error cases.
   - For data classes or models, describe invariants and typical construction paths.

4) Add inline comments for complex logic.
   - Focus on normalization/mapping functions, time calculations, and validation branching.
   - Explain why certain fields are normalized or mapped in specific ways.

5) Update `docs/classes_seva.md`.
   - Add a section for domain types, including the “Mode Registry” and how it normalizes/validates modes.
   - Explain parameter classes (CV/DC/AC/EIS/etc.) and how they are used in the GUI and API calls.

6) Final pass.
   - Confirm Google-style docstrings across all files.
   - Confirm call-chain and error cases are documented for every public API.

## Concrete Steps

All steps are run from the repository root (`/workspace/SEVA_GUI_MVVM`).

1) Inspect domain files:

    sed -n '1,200p' seva/domain/ports.py
    sed -n '1,200p' seva/domain/models.py
    sed -n '1,200p' seva/domain/entities.py
    sed -n '1,200p' seva/domain/modes.py
    sed -n '1,200p' seva/domain/errors.py
    sed -n '1,200p' seva/domain/validation.py
    sed -n '1,200p' seva/domain/mapping.py
    sed -n '1,200p' seva/domain/params/cv.py
    sed -n '1,200p' seva/domain/params/dc.py
    sed -n '1,200p' seva/domain/params/ac.py
    sed -n '1,200p' seva/domain/params/eis.py
    sed -n '1,200p' seva/domain/params/cdl.py

2) Add/expand docstrings and inline comments in each file.

3) Update `docs/classes_seva.md` with domain overview and relationships.

4) Validation:

    pytest -q

5) Coverage validation for module/class/function docstrings:

    python - <<'PY'
    import ast
    from pathlib import Path
    root = Path("seva/domain")
    missing = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if ast.get_docstring(tree) is None:
            missing.append(f"{path}:module")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(node) is None:
                    missing.append(f"{path}:{node.name}@{node.lineno}")
    print("docstring-check: OK (no missing module/class/function docstrings)" if not missing else "\n".join(missing))
    PY

## Validation and Acceptance

- Every file in `seva/domain` and `seva/domain/params` has a Google-style module docstring.
- Every class/function has a Google-style docstring with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments clarify complex normalization/validation logic.
- `docs/classes_seva.md` documents domain entities, DTOs, mode registry, and parameter schemas.

## Idempotence and Recovery

Documentation changes are safe and repeatable. Revert any incorrect docstrings with `git restore <file>` and reapply the documentation updates only.

## Artifacts and Notes

Expected artifacts:

- Updated domain docstrings in `seva/domain/*.py` and `seva/domain/params/*.py`.
- Updated `docs/classes_seva.md` with domain section.

Validation snippets:

    docstring-check: OK (no missing module/class/function docstrings)

    ........                                                                 [100%]
    8 passed in 0.16s

Example Google-style docstring:

    """Short summary.

    Longer description about where this is used, who calls it, and why it exists.

    Args:
        param1: Description.

    Returns:
        Description.

    Raises:
        DomainError: If validation fails.
    """

## Interfaces and Dependencies

No new dependencies are introduced. Interfaces to highlight include:

- Port definitions in `seva/domain/ports.py`
- Mode registry in `seva/domain/modes.py`
- Parameter schemas in `seva/domain/params/*.py`

---

Change note: Updated living sections to reflect completed implementation milestones, recorded decisions/discoveries, and added validation evidence snippets.
