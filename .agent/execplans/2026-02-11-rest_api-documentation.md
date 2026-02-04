# Document rest_api module in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

The REST API is the downstream contract the GUI depends on. This plan produces exhaustive documentation for every file in `rest_api/` so a new developer can understand each endpoint, validation rule, storage layout, and NAS integration without reading the code first. The result should be a self-explanatory API module where module-level docstrings, class/function docstrings, and inline comments explain how requests flow from the GUI into FastAPI handlers and out to storage or device operations.

Success is observable when:

- Every `rest_api/*.py` file starts with a NumPy-style module docstring that describes purpose, dependencies, typical call contexts, and error cases.
- Every function/class has a NumPy-style docstring that includes parameters, returns, side effects, typical call-chain, usage scenarios, and error handling.
- `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` contain updated, detailed documentation for REST API types, endpoints, and workflows.

## Progress

- [ ] (2026-02-11 00:00Z) Inventory and map all `rest_api/` modules and their relationships to GUI calls.
- [ ] (2026-02-11 00:00Z) Add or rewrite module docstrings for `rest_api/` with NumPy style, focusing on purpose, dependencies, and call contexts.
- [ ] (2026-02-11 00:00Z) Add/expand class and function docstrings for each module, including call-chain and error cases.
- [ ] (2026-02-11 00:00Z) Add inline comments to complex logic (validation, storage layout, progress calculation, NAS operations).
- [ ] (2026-02-11 00:00Z) Update `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` with detailed descriptions and diagrams.
- [ ] (2026-02-11 00:00Z) Run a final consistency check for NumPy style, completeness, and linkage to GUI usecases.

## Surprises & Discoveries

- Observation: None yet.
  Evidence: Plan initialization only.

## Decision Log

- Decision: Use NumPy-style docstrings for all files in `rest_api/`.
  Rationale: User requirement and to keep REST API docstrings consistent.
  Date/Author: 2026-02-11 / Agent

## Outcomes & Retrospective

- Status: Not started. This section will be updated after milestones and completion.

## Context and Orientation

The `rest_api/` directory contains the FastAPI application that the GUI (`seva/`) calls to validate experiment parameters, start jobs, poll status, cancel runs, and download results. The API defines the authoritative status and progress values; the GUI must not fabricate these. The API also encapsulates storage layout, progress calculations, and optional NAS access.

Key files (non-exhaustive):

- `rest_api/app.py`: FastAPI app and route definitions.
- `rest_api/validation.py`: parameter validation rules and error shaping.
- `rest_api/progress_utils.py`: progress/remaining-time calculations.
- `rest_api/storage.py`: run folder layout, file operations, zip packaging.
- `rest_api/nas.py` and `rest_api/nas_smb.py`: NAS access and SMB integration.
- `rest_api/auto_flash_linux.py`: firmware auto-flash utility.

“Call-chain” in this plan means the path from GUI usecases (e.g., `seva/usecases/start_experiment_batch.py`) through adapters (`seva/adapters/*`) into specific API endpoints.

## Plan of Work

1) Inventory the REST API entrypoints and map their GUI callers.
   - Read `rest_api/app.py` and enumerate every route, HTTP method, and response type.
   - Trace each endpoint back to GUI adapter calls (e.g., device/job adapters) and note the usecases that trigger those adapters.
   - Capture this map in `docs/workflows_rest_api.md` as a call-chain list and in-line references.

2) Document each REST API module in depth.
   - Add a module docstring at the top of each `rest_api/*.py` file (NumPy style). The docstring must include: purpose, role in system, upstream callers (GUI adapters/usecases), downstream dependencies (filesystem, NAS, device libs), and typical error cases.
   - For each class/function, add a NumPy-style docstring with:
     - Short summary line
     - Extended description (what and why)
     - Parameters/Returns
     - Side effects (filesystem writes, device access, network calls)
     - Typical call-chain context
     - Usage scenarios (e.g., “triggered when user clicks Start”)
     - Error cases (validation failures, missing files, device offline)

3) Add inline comments for complex logic.
   - Focus on: validation branches, progress calculations, storage path normalization, NAS authentication, and job lifecycle state transitions.
   - Comments should explain why branches exist, not restate the code.

4) Update `docs/classes_rest_api.md`.
   - Describe each module and its public API surfaces.
   - Include references to the key functions/classes in each file.
   - Note how each module interacts with storage or device-side processes.

5) Update `docs/workflows_rest_api.md`.
   - Add end-to-end workflow descriptions:
     - Validate → Start → Poll → Download
     - Cancel and cleanup flows
     - Admin or discovery flows (if present)
   - Include a Mermaid sequence diagram showing GUI → adapter → REST endpoint → storage/device path.

6) Final pass.
   - Confirm NumPy style is used consistently.
   - Confirm every file has a module docstring.
   - Confirm all docstrings mention call-chains and error cases.

## Concrete Steps

All steps are run from the repository root (`/workspace/SEVA_GUI_MVVM`).

1) Inspect REST API files:

    sed -n '1,200p' rest_api/app.py
    sed -n '1,200p' rest_api/validation.py
    sed -n '1,200p' rest_api/progress_utils.py
    sed -n '1,200p' rest_api/storage.py
    sed -n '1,200p' rest_api/nas.py
    sed -n '1,200p' rest_api/nas_smb.py
    sed -n '1,200p' rest_api/auto_flash_linux.py

2) Add/expand docstrings and inline comments in each file.

3) Update docs:

    mkdir -p docs
    $EDITOR docs/classes_rest_api.md
    $EDITOR docs/workflows_rest_api.md

4) Optional validation (documentation only):

    pytest -q

## Validation and Acceptance

- Every `rest_api/*.py` file contains a NumPy-style module docstring that explains purpose, role, and call-chain context.
- Every function/class has a NumPy-style docstring with parameters, returns, side effects, call-chain, usage scenarios, and error cases.
- Inline comments exist only where logic is complex and explain the rationale.
- `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` document endpoint responsibilities and GUI integrations.

## Idempotence and Recovery

Documentation edits are safe and repeatable. If a docstring change is incorrect, revert the file and reapply documentation only. Avoid changing logic. Use `git restore <file>` to revert if needed.

## Artifacts and Notes

Expected artifacts:

- Updated `rest_api/*.py` docstrings and inline comments.
- `docs/classes_rest_api.md`
- `docs/workflows_rest_api.md`

Example NumPy-style module docstring:

    """REST API module summary.

    Extended description describing upstream GUI callers, storage dependencies,
    and typical error cases.
    """

## Interfaces and Dependencies

No new dependencies are added. The plan documents existing FastAPI routes and their interactions with filesystem and NAS access. Interfaces to highlight include:

- REST endpoints in `rest_api/app.py`
- Storage helpers in `rest_api/storage.py`
- Validation helpers in `rest_api/validation.py`

---

Change note: Initial plan created to cover only the REST API subsystem in deep detail.
