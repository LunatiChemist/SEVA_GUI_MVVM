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

- [ ] (2026-02-11 00:00Z) Map the domain model and how it is used by usecases/adapters.
- [ ] (2026-02-11 00:00Z) Add/expand module docstrings for every file in `seva/domain` and `seva/domain/params`.
- [ ] (2026-02-11 00:00Z) Add/expand class and function docstrings including call-chain and error cases.
- [ ] (2026-02-11 00:00Z) Add inline comments for complex mapping, normalization, and validation logic.
- [ ] (2026-02-11 00:00Z) Update `docs/classes_seva.md` with domain entities, DTOs, and mode registry details.
- [ ] (2026-02-11 00:00Z) Final consistency pass for Google style and completeness.

## Surprises & Discoveries

- Observation: None yet.
  Evidence: Plan initialization only.

## Decision Log

- Decision: Use Google-style docstrings for all files in `seva/domain` and `seva/domain/params`.
  Rationale: User requirement and alignment with GUI subsystem documentation.
  Date/Author: 2026-02-11 / Agent

## Outcomes & Retrospective

- Status: Not started. This section will be updated after milestones and completion.

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

4) Optional validation (documentation only):

    pytest -q

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

Change note: Initial plan created to cover the domain subsystem in deep detail.
