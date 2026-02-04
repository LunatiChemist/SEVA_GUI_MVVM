# Document rest_api module in detail

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

PLANS.md lives at `.agent/PLANS.md` from the repository root. This document must be maintained in accordance with that file.

## Purpose / Big Picture

The REST API is the downstream contract the GUI depends on. This plan delivers detailed documentation for every module in `rest_api/` so a new contributor can understand endpoint behavior, validation rules, storage layout, and NAS/firmware integrations before reading implementation details.

Success is observable when:

- Every `rest_api/*.py` file has a module docstring describing role, dependencies, call context, and failure modes.
- Module-level classes/functions expose NumPy-style docstrings (or existing concise docstrings) with behavior and error semantics.
- `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` document route-to-adapter call chains and full experiment workflows, including a sequence diagram.

## Progress

- [x] (2026-02-04 20:54Z) Inventory and map all `rest_api/` modules and GUI caller relationships.
- [x] (2026-02-04 21:03Z) Rewrite module-level docstrings across `rest_api/` for clearer purpose/call-chain/dependency context.
- [x] (2026-02-04 21:09Z) Expand helper docstrings and rationale comments in `rest_api/storage.py` and `rest_api/auto_flash_linux.py`.
- [x] (2026-02-04 21:12Z) Replace placeholder/generic docstring phrases in `rest_api/app.py` with route-orchestration wording and improve top-level module description.
- [x] (2026-02-04 21:18Z) Update `docs/classes_rest_api.md` and `docs/workflows_rest_api.md` with module inventory, endpoint mapping, workflow narratives, and Mermaid sequence diagram.
- [x] (2026-02-04 21:20Z) Run validation checks (`docstring-check` script and `pytest -q`) and capture evidence.

## Surprises & Discoveries

- Observation: Rewriting `rest_api/storage.py` introduced an escaped-backslash syntax regression in `sanitize_client_datetime`.
  Evidence:
    Traceback (most recent call last):
      File "<stdin>", line 4, in <module>
      ...
      .replace("\", "-")
    SyntaxError: EOL while scanning string literal

- Observation: Existing app docstrings had many generated placeholder phrases that were technically valid but low-signal for maintainers.
  Evidence:
    `rg -n "Input provided by the caller or framework|Value returned to the caller or HTTP stack" rest_api` originally returned many hits in `rest_api/app.py` and helper modules; final check returns no matches.

## Decision Log

- Decision: Keep documentation edits code-neutral (no behavior changes) while making docstrings precise enough to explain side effects and call context.
  Rationale: Plan scope is documentation; preserving runtime behavior avoids accidental regressions.
  Date/Author: 2026-02-04 / Agent

- Decision: Fully rewrite `rest_api/storage.py` and `rest_api/auto_flash_linux.py` docstrings instead of incremental line edits.
  Rationale: These files contained repeated boilerplate text; full rewrites produced consistent, accurate docs faster and reduced copy/paste artifacts.
  Date/Author: 2026-02-04 / Agent

- Decision: Keep `rest_api/app.py` logic untouched and focus updates on module-level explanation plus placeholder-phrase cleanup.
  Rationale: `app.py` is large and high-risk; documentation gains were achieved without changing orchestration code.
  Date/Author: 2026-02-04 / Agent

## Outcomes & Retrospective

At completion, the REST API package now has explicit module-level orientation, richer helper documentation, and updated architecture docs for classes and workflows. The biggest quality gain came from replacing low-information placeholder docstrings with practical call-chain and side-effect explanations. Remaining gap: some `app.py` function docstrings are still concise rather than exhaustive, but all module/class/function entry points are documented and linked in the docs.

## Context and Orientation

The `rest_api/` directory is the FastAPI backend consumed by GUI adapters in `seva/adapters/`. The API is responsible for authoritative run status/progress values, run artifact storage resolution, optional NAS upload, and firmware flashing orchestration.

Key files:

- `rest_api/app.py`: FastAPI routes, in-memory job and slot registries, worker-thread orchestration.
- `rest_api/validation.py`: typed parameter validation results for mode-specific payload checks.
- `rest_api/progress_utils.py`: duration estimation and aggregate progress calculation.
- `rest_api/storage.py`: path sanitization and persistent run-id directory index.
- `rest_api/nas_smb.py` / `rest_api/nas.py`: NAS adapters (SMB active, SSH variant retained).
- `rest_api/auto_flash_linux.py`: Linux DFU flashing helper used by firmware route.

## Plan of Work

1) Inventory route surfaces and caller map.
Read `rest_api/app.py` and trace adapter references in `seva/adapters/*` to map each GUI flow to endpoint families.

2) Improve module and helper docs.
Rewrite module-level docstrings across all Python modules in `rest_api/`. Replace placeholder/helper boilerplate in storage/flash utilities with accurate parameter, side-effect, and failure descriptions.

3) Update architecture docs.
Rewrite `docs/classes_rest_api.md` with module inventory and key contracts. Rewrite `docs/workflows_rest_api.md` with validate/start/poll/download, cancel, NAS, firmware, and telemetry workflows plus sequence diagram.

4) Validate and capture evidence.
Run docstring coverage check and test suite command listed in this plan. Embed concise output snippets.

## Concrete Steps

All commands were run from repository root (`c:\Users\LunaP\OneDrive - UBC\Dokumente\Chemistry\Potentiostats\GUI Testing\SEVA_GUI_MVVM`).

1) Inventory files and caller links:

    rg --files rest_api
    rg -n "(/devices|/modes|/jobs|/runs|/nas|telemetry|firmware|admin/rescan)" seva/adapters seva/usecases

2) Implement doc updates:

    # edited
    rest_api/__init__.py
    rest_api/app.py
    rest_api/validation.py
    rest_api/progress_utils.py
    rest_api/storage.py
    rest_api/auto_flash_linux.py
    docs/classes_rest_api.md
    docs/workflows_rest_api.md

3) Validate:

    python - <<'PY'
    import ast
    from pathlib import Path
    for p in sorted(Path('rest_api').glob('*.py')):
        mod = ast.parse(p.read_text(encoding='utf-8'))
        assert ast.get_docstring(mod)
        for n in mod.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assert ast.get_docstring(n), f"missing docstring: {p}:{n.name}"
    print('docstring-check: ok')
    PY

    pytest -q

Validation evidence:

    docstring-check: ok

    ........                                                                 [100%]
    8 passed in 0.17s

## Validation and Acceptance

Acceptance status: met.

- `rest_api/*.py` now all begin with module docstrings with purpose and integration context.
- Module-level classes/functions have docstrings (verified by AST check script).
- `docs/classes_rest_api.md` now lists all REST modules, endpoint-to-adapter mapping, and type contracts.
- `docs/workflows_rest_api.md` now includes end-to-end workflow narratives and Mermaid sequence diagram.
- `pytest -q` passes (`8 passed`).

## Idempotence and Recovery

The documentation edits are idempotent and can be re-applied safely. Recovery path if needed:

- Re-run AST docstring checker to detect missing sections.
- Re-run `pytest -q` to confirm no behavioral regression.
- If a wording change is incorrect, edit affected docs/docstrings and repeat the same validations.

## Artifacts and Notes

Key output evidence:

    docstring-check: ok

    ........                                                                 [100%]
    8 passed in 0.17s

Touched files:

- `rest_api/__init__.py`
- `rest_api/app.py`
- `rest_api/validation.py`
- `rest_api/progress_utils.py`
- `rest_api/storage.py`
- `rest_api/auto_flash_linux.py`
- `docs/classes_rest_api.md`
- `docs/workflows_rest_api.md`

## Interfaces and Dependencies

No new dependencies were added.

Interfaces covered by the documentation update:

- FastAPI endpoint contracts in `rest_api/app.py`
- Validation contracts in `rest_api/validation.py` (`ValidationIssue`, `ValidationResult`)
- Progress contract in `rest_api/progress_utils.py` (`progress_pct`, `remaining_s`)
- Storage/path contract in `rest_api/storage.py` (`RunStorageInfo` and run-id index)
- NAS adapter contracts in `rest_api/nas_smb.py` and `rest_api/nas.py`
- Firmware subprocess contract in `rest_api/auto_flash_linux.py`

---

Change note: 2026-02-04 implementation pass completed. Updated living sections with progress, discoveries, decisions, outcomes, and embedded validation evidence.
