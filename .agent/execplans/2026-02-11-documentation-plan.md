# Document SEVA GUI MVVM codebase (rest_api + seva)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

The goal is a fully documented, easy-to-understand codebase for the GUI (`seva/`) and the Pi REST API (`rest_api/`). After completing this work, a new developer can read any file in these folders and understand the file’s purpose, how it fits the system, and the call-chain that reaches it. The documentation should also explain end‑to‑end workflows (start, poll, download, cancel, discovery, etc.) and the architecture boundaries (MVVM + Hexagonal). The results must be visible in two places: (1) in-code docstrings and inline comments, and (2) new documents under `docs/` that explain classes and workflows at a high level.

## Progress

- [x] (2026-02-03 23:06Z) Create docs folder structure and stubs for class/workflow documents.
- [x] (2026-02-03 23:10Z) Analyze `rest_api/` modules and add file/class/function docstrings + inline comments; update docs for REST API classes/workflows.
- [x] (2026-02-03 23:15Z) Analyze `seva/domain` and `seva/domain/params` and add file/class/function docstrings + inline comments; update docs for core domain models/workflows.
- [x] (2026-02-03 23:18Z) Analyze `seva/adapters` and add docstrings + inline comments; update docs for adapter interfaces and API integration.
- [x] (2026-02-03 23:54Z) Analyze `seva/usecases` and add docstrings + inline comments; update docs for orchestration workflows.
- [x] (2026-02-04 00:00Z) Analyze `seva/viewmodels` and add docstrings + inline comments; update docs for UI state + commands.
- [x] (2026-02-04 00:00Z) Analyze `seva/app` and `seva/app/views` and add docstrings + inline comments; update docs for UI composition and controllers.
- [x] (2026-02-04 00:02Z) Final review pass to ensure style compliance, call-chain completeness, and documentation coverage.

## Surprises & Discoveries

- Observation: The repository already had a `docs/` directory with an empty `docs/workflows/` subdirectory, so the milestone created documentation files in-place rather than creating a brand-new docs root.
  Evidence: `Get-ChildItem docs` listed an existing folder before file creation.
- Observation: `rest_api/` includes a `rest_api/tests` folder discovered during compile validation, even though it is not part of the primary documentation scope.
  Evidence: `python -m compileall rest_api` emitted `Listing 'rest_api\\tests'...`.
- Observation: `seva/domain/models.py`, `seva/domain/errors.py`, and `seva/domain/validation.py` were empty placeholder files.
  Evidence: File length checks returned `0` bytes for all three files before documentation updates.
- Observation: `seva/adapters/__init__.py` was empty before documentation and required a package-level docstring to satisfy module coverage requirements.
  Evidence: Reading `seva/adapters/__init__.py` returned no content prior to edits.
- Observation: `seva/usecases/load_device_status.py` is currently an empty placeholder module.
  Evidence: File inspection showed no executable content before adding module-level documentation.
- Observation: Some UI files already contained mojibake text fragments (for example `â€”` and `Choose Results Dirâ€¦`) before this documentation pass.
  Evidence: Existing literals in `seva/app/views/discovery_results_dialog.py` and `seva/app/views/settings_dialog.py` were preserved while adding docstrings.
- Observation: Final global coverage checks surfaced two remaining undocumented runtime files (`seva/__init__.py`, `seva/utils/logging.py`) outside earlier subsystem milestones.
  Evidence: The first global coverage pass reported `missing_count= 5` for those files/functions before final fixes.


## Decision Log

- Decision: Use Google-style docstrings for `seva/` and NumPy-style docstrings for `rest_api/`.
  Rationale: User requirement for docstring style alignment by subsystem.
  Date/Author: 2026-02-11 / Agent

- Decision: Create multiple docs files by subsystem rather than a single large document.
  Rationale: The repo has distinct subsystems and many modules; per-subsystem docs remain navigable and scoped.
  Date/Author: 2026-02-11 / Agent

- Decision: Add `docs/architecture_overview.md` in addition to the four required docs files.
  Rationale: A single cross-system orientation page improves onboarding and keeps subsystem docs focused.
  Date/Author: 2026-02-03 / Agent

- Decision: Use a scripted pass to add missing NumPy-style module/class/function docstrings across `rest_api/` and then manually curate `docs/classes_rest_api.md` and `docs/workflows_rest_api.md`.
  Rationale: `rest_api/app.py` and helper modules had many missing docstrings; scripted insertion ensured complete coverage quickly while preserving runtime behavior.
  Date/Author: 2026-02-03 / Agent

- Decision: Keep `seva/domain/models.py`, `seva/domain/errors.py`, and `seva/domain/validation.py` as documented placeholders instead of deleting them.
  Rationale: They are referenced as stable extension points/compatibility locations; deleting them was not required by this plan and could break imports.
  Date/Author: 2026-02-03 / Agent

- Decision: Apply the same scripted docstring-completion approach to `seva/adapters` as used for `rest_api` and domain files.
  Rationale: Adapter coverage required module docstrings across many files plus a small set of missing helper docs; scripted insertion kept the effort consistent and low risk.
  Date/Author: 2026-02-03 / Agent

- Decision: Keep `seva/usecases/load_device_status.py` as a documented placeholder instead of deleting it.
  Rationale: It signals planned use-case expansion and removing it is outside this documentation-only scope.
  Date/Author: 2026-02-03 / Agent

- Decision: Preserve existing legacy utility modules (`seva/app/dataplotter_standalone.py`, `seva/app/nas_gui_smb.py`) and document them in-place.
  Rationale: The plan is documentation-only and these modules are still reachable from UI entry points or standalone tooling.
  Date/Author: 2026-02-04 / Agent

- Decision: Keep tests unchanged and exclude `*/tests/*` files from strict docstring-coverage checks during final validation.
  Rationale: The acceptance criteria required tests to remain unchanged; coverage validation therefore targets runtime code paths.
  Date/Author: 2026-02-04 / Agent


## Outcomes & Retrospective

- Milestone 1 outcome (2026-02-03): Documentation scaffold is in place with the four required docs files plus an architecture overview file. Remaining milestones now focus on in-code docstring/comment coverage and filling these docs with subsystem details.
- Milestone 2 outcome (2026-02-03): All `rest_api/*.py` files now have module docstrings, and every top-level class/function has a NumPy-style docstring. REST API class and workflow documents were filled with endpoint, model, and call-chain descriptions.
- Milestone 3 outcome (2026-02-03): Domain and domain-params coverage is complete with Google-style module/class/function docstrings, and SEVA docs now include detailed domain module and workflow sections.
- Milestone 4 outcome (2026-02-03): Adapter documentation coverage is complete (module/class/function docstrings) and SEVA docs now include adapter-to-port mappings plus adapter call-chain workflows.
- Milestone 5 outcome (2026-02-03): Use-case module/class/function doc coverage is complete, including central error-mapping helpers and orchestration classes; SEVA workflow docs now describe start/poll/download/cancel/discovery orchestration.
- Milestone 6 outcome (2026-02-04): ViewModel module coverage is complete with Google-style docstrings for module/class/function gaps, including status-format helper functions and runs-row model documentation.
- Milestone 7 outcome (2026-02-04): `seva/app` and `seva/app/views` coverage is complete, including controller/presenter modules and remaining view modules; SEVA class/workflow docs now include full UI composition call-chains.
- Milestone 8 outcome (2026-02-04): Final consistency validation passed. Remaining undocumented package/util files were fixed, global non-test coverage reached zero missing docstrings, docs artifacts are present, and test suite remains green (`8 passed`).

## Context and Orientation

This repository contains a Tkinter GUI (`seva/`) that controls electrochemistry experiments via a FastAPI service (`rest_api/`). The GUI uses MVVM + Hexagonal architecture, meaning:

- Views (`seva/app/views`) handle UI rendering only.
- ViewModels (`seva/viewmodels`) hold UI state and commands; they must not perform I/O.
- UseCases (`seva/usecases`) orchestrate workflows (start, validate, poll, cancel, download, discovery, etc.).
- Adapters (`seva/adapters`) implement ports to external systems (HTTP API, filesystem, device discovery).
- Domain models and ports live in `seva/domain` and define shared types, validation, and mode registry.

The REST API (`rest_api/`) is a FastAPI application that validates experiment parameters, creates jobs, reports status, and serves run artifacts. It is the downstream service that the GUI interacts with. The GUI’s workflows should be explained in terms of their calls into this API.

This plan focuses on documentation only. It will not change runtime behavior or business logic, but will insert or update docstrings and inline comments, and create `docs/` documents describing classes and workflows.

Definitions:

- “Call-chain” means the typical path of function calls from a UI event or entry point through viewmodels and usecases to adapters and REST calls.
- “Workflow” means a multi-step user-visible flow (e.g., start experiment, poll status, download results) and its sequence of usecase and adapter interactions.

Key locations (non-exhaustive):

- GUI entry points: `seva/app/main.py`, `seva/app/controller.py`, `seva/app/run_flow_presenter.py`.
- Views: `seva/app/views/*.py`.
- ViewModels: `seva/viewmodels/*.py`.
- UseCases: `seva/usecases/*.py`.
- Adapters: `seva/adapters/*.py`.
- Domain: `seva/domain/*.py` and `seva/domain/params/*.py`.
- REST API: `rest_api/app.py`, `rest_api/validation.py`, `rest_api/progress_utils.py`, `rest_api/storage.py`, `rest_api/nas.py`, `rest_api/nas_smb.py`.

## Plan of Work

The documentation work will proceed from outer API contracts to inner GUI layers, ensuring call-chains are understood before editing docstrings.

1) Create documentation files under `docs/` and define the target structure:
   - `docs/classes_seva.md`
   - `docs/workflows_seva.md`
   - `docs/classes_rest_api.md`
   - `docs/workflows_rest_api.md`
   - Optional: `docs/architecture_overview.md` if a brief cross-system view adds clarity.
   These docs will include Mermaid diagrams where they add value, such as a sequence diagram for Start → Validate → Create Jobs → Poll → Download, and an architecture diagram for MVVM + Hexagonal layers.

2) Document `rest_api/` first.
   - Read each module and identify the entrypoints, helper functions, and types.
   - Add a module docstring at the top of each file (NumPy style) describing purpose, role in system, dependencies, and typical call contexts.
   - Add class docstrings and function docstrings with: short summary, parameters, returns, side effects, typical call-chains, usage scenarios, and error cases.
   - Add inline comments only for complex logic (validation, progress calculations, storage layout, NAS integration).
   - Update `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` with references to API endpoints and related modules.

3) Document `seva/domain/` and `seva/domain/params/`.
   - Identify the “Mode Registry” module and any domain objects that should be central to documentation.
   - Add module docstrings (Google style), class docstrings, and function docstrings with call-chains and error cases.
   - Add inline comments for complex mapping/normalization logic and parameter validation.
   - Update `docs/classes_seva.md` with core domain types and relationships.

4) Document `seva/adapters/`.
   - Map each adapter to the port interface it implements (likely in `seva/domain/ports.py`).
   - Add module/class/function docstrings describing external dependencies (HTTP API, filesystem), normalization points, and error propagation.
   - Add inline comments on complex parsing or error handling.
   - Update `docs/classes_seva.md` and `docs/workflows_seva.md` to reflect adapter involvement.

5) Document `seva/usecases/`.
   - For each usecase, identify input DTOs/domain models and adapter dependencies.
   - Add docstrings that explain the workflow steps and where server-authoritative status is used.
   - Add inline comments to clarify orchestration steps and branching logic.
   - Update `docs/workflows_seva.md` with step-by-step flows and participating classes.

6) Document `seva/viewmodels/`.
   - Add docstrings describing UI state, commands, and how they trigger usecases.
   - Clearly mention what each VM expects from adapters/usecases (without duplicating domain logic).
   - Update `docs/classes_seva.md` to include viewmodel responsibilities.

7) Document `seva/app/` and `seva/app/views/`.
   - Add module docstrings for controllers and views describing how UI elements connect to viewmodels and present data.
   - Add inline comments only where UI logic is complex (layout, event binding, or conditional UI rendering).
   - Update `docs/workflows_seva.md` to show UI entrypoints for flows.

8) Perform a final consistency pass.
   - Ensure all docstrings are English, match requested style, and mention call-chains and error cases.
   - Ensure file-level docstrings appear at the top of every file in scope.
   - Ensure `rest_api/` uses NumPy style, `seva/` uses Google style.
   - Confirm tests in `seva/tests/` remain unchanged (not documented).

## Concrete Steps

All steps are run from the repository root (`/workspace/SEVA_GUI_MVVM`).

1) Create `docs/` directory and stub documents:

    mkdir -p docs
    printf "# SEVA Classes\n" > docs/classes_seva.md
    printf "# SEVA Workflows\n" > docs/workflows_seva.md
    printf "# REST API Classes\n" > docs/classes_rest_api.md
    printf "# REST API Workflows\n" > docs/workflows_rest_api.md

2) Document REST API files:

    # Open each file to inspect its contents
    sed -n '1,200p' rest_api/app.py
    sed -n '1,200p' rest_api/validation.py
    sed -n '1,200p' rest_api/progress_utils.py
    sed -n '1,200p' rest_api/storage.py
    sed -n '1,200p' rest_api/nas.py
    sed -n '1,200p' rest_api/nas_smb.py

    # Edit each file to add/extend docstrings and inline comments.

3) Document domain models and parameters:

    sed -n '1,200p' seva/domain/ports.py
    sed -n '1,200p' seva/domain/models.py
    sed -n '1,200p' seva/domain/modes.py
    sed -n '1,200p' seva/domain/params/cv.py
    # Continue for the remaining domain files.

4) Document adapters:

    sed -n '1,200p' seva/adapters/http_client.py
    sed -n '1,200p' seva/adapters/device_rest.py
    sed -n '1,200p' seva/adapters/job_rest.py
    # Continue for remaining adapters.

5) Document usecases:

    sed -n '1,200p' seva/usecases/start_experiment_batch.py
    sed -n '1,200p' seva/usecases/poll_group_status.py
    sed -n '1,200p' seva/usecases/download_group_results.py
    # Continue for remaining usecases.

6) Document viewmodels and views:

    sed -n '1,200p' seva/viewmodels/experiment_vm.py
    sed -n '1,200p' seva/app/views/experiment_panel_view.py
    # Continue for remaining viewmodels and views.

7) Update docs files with summaries, class lists, and workflows.

8) Run formatting checks or linting if available (optional). If no tools are configured, skip this step.

## Validation and Acceptance

Validation is documentation-focused, so the acceptance criteria are human-verifiable:

- Every Python file in `rest_api/` and `seva/` has a top-level module docstring describing purpose, system role, dependencies, and typical call contexts.
- Every class and function has a docstring that includes: short summary, parameters, returns, side effects, typical call-chain, usage scenario, and error cases.
- Docstrings follow style requirements: Google style in `seva/`, NumPy style in `rest_api/`.
- Inline comments appear in complex logic areas only, clarifying intermediate steps and rationale.
- `docs/` contains at least the four core documents with clear class and workflow descriptions.
- REST API docs explicitly describe how the GUI uses the API endpoints.
- Tests under `seva/tests/` are left unchanged.

If desired, optionally run `pytest -q` to ensure no behavioral changes were introduced. Expected output should show tests passing; documentation-only changes should not affect test outcomes.

## Idempotence and Recovery

Documentation edits are safe and repeatable. If a docstring change is incorrect, revert or edit the docstring without affecting runtime logic. When adding inline comments, avoid modifying code logic; if a mistake is made, revert with `git checkout -- <file>` or `git restore <file>` and reapply the documentation change only.

## Artifacts and Notes

Expected artifacts:

- `docs/classes_seva.md`
- `docs/workflows_seva.md`
- `docs/classes_rest_api.md`
- `docs/workflows_rest_api.md`
- Optional: `docs/architecture_overview.md` (if needed for clarity)

Milestone 1 evidence:

    > rg --files docs
    docs\workflows_seva.md
    docs\workflows_rest_api.md
    docs\classes_rest_api.md
    docs\architecture_overview.md
    docs\classes_seva.md

Milestone 2 evidence:

    > python -m compileall rest_api
    Listing 'rest_api'...
    Compiling 'rest_api\app.py'...
    Compiling 'rest_api\storage.py'...
    Listing 'rest_api\tests'...
    Compiling 'rest_api\validation.py'...

    > python - <<'PY'
    ... docstring coverage check for rest_api ...
    ... print("missing_count=", len(missing))
    ... PY
    missing_count= 0

Milestone 3 evidence:

    > python -m compileall seva/domain
    Listing 'seva/domain'...
    Compiling 'seva/domain\entities.py'...
    Listing 'seva/domain\params'...
    Compiling 'seva/domain\snapshot_normalizer.py'...
    Compiling 'seva/domain\validation.py'...

    > python - <<'PY'
    ... domain + params docstring coverage check ...
    ... print("missing_count=", len(missing))
    ... PY
    missing_count= 0

Milestone 4 evidence:

    > python -m compileall seva/adapters
    Listing 'seva/adapters'...
    Compiling 'seva/adapters\device_rest.py'...
    Compiling 'seva/adapters\job_rest.py'...
    Compiling 'seva/adapters\storage_local.py'...

    > python - <<'PY'
    ... adapters docstring coverage check ...
    ... print("missing_count=", len(missing))
    ... PY
    missing_count= 0

Milestone 5 evidence:

    > python -m compileall seva/usecases
    Listing 'seva/usecases'...
    Compiling 'seva/usecases\start_experiment_batch.py'...
    Compiling 'seva/usecases\poll_group_status.py'...
    Compiling 'seva/usecases\run_flow_coordinator.py'...

    > python - <<'PY'
    ... usecases docstring coverage check ...
    ... print("missing_count=", len(missing))
    ... PY
    missing_count= 0

Milestone 6-7 evidence:

    > python -m compileall seva/viewmodels seva/app
    Listing 'seva/viewmodels'...
    Compiling 'seva/viewmodels\progress_vm.py'...
    Listing 'seva/app'...
    Compiling 'seva/app\main.py'...
    Listing 'seva/app\views'...
    Compiling 'seva/app\views\experiment_panel_view.py'...

    > python - <<'PY'
    ... viewmodels + app docstring coverage check ...
    ... print("checked_files=", len(checked))
    ... print("missing_count=", len(missing))
    ... PY
    checked_files= 29
    missing_count= 0
Milestone 8 evidence:

    > python - <<'PY'
    ... global non-test docstring coverage check ...
    ... print("checked_files=", checked)
    ... print("missing_count=", len(missing))
    ... PY
    checked_files= 94
    missing_count= 0

    > python -m compileall rest_api seva
    Listing 'rest_api'...
    Listing 'seva'...
    Listing 'seva\app'...
    Compiling 'seva\utils\logging.py'...

    > pytest -q
    ........                                                                 [100%]
    8 passed in 0.18s

    > rg --files docs
    docs\workflows_seva.md
    docs\workflows_rest_api.md
    docs\classes_seva.md
    docs\classes_rest_api.md
    docs\architecture_overview.md


Example documentation snippet (Google style, for `seva/`):

    """Brief summary.

    Detailed context about where this function is called from, what workflows
    it participates in, and how it interacts with adapters or domain models.

    Args:
        param1: Description.

    Returns:
        Description.

    Raises:
        SomeError: When something goes wrong.
    """

Example documentation snippet (NumPy style, for `rest_api/`):

    """Brief summary.

    Extended description about API usage and call contexts.

    Parameters
    ----------
    param1 : str
        Description.

    Returns
    -------
    bool
        Description.

    Raises
    ------
    ValueError
        When validation fails.
    """

## Interfaces and Dependencies

This plan does not add new dependencies. It documents existing interfaces only. Key interfaces include:

- `seva/domain/ports.py`: defines ports for device/job/storage/discovery interactions.
- `seva/adapters/*`: implement those ports for REST API and local storage.
- `seva/usecases/*`: orchestrate workflows such as start, poll, cancel, download, test connection, and discovery.
- `rest_api/app.py`: defines FastAPI routes used by the GUI.

No external services are required for documentation changes, but understanding call-chains may require tracing endpoints defined in `rest_api/app.py` and the adapter calls in `seva/adapters/*`.

---

Change note (2026-02-04): Completed final review milestone, fixed remaining package/logging documentation gaps, and added final global validation evidence (coverage, compile, docs artifacts, tests).
