# Implement remote package update across all boxes (REST API + GUI + ZIP generator)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be updated continuously during implementation.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

After this change, an operator can upload one update ZIP from the Settings area and trigger an asynchronous update flow that applies to all configured boxes. The backend validates the package, updates only the included components (REST API, pyBEEP, firmware), flashes firmware using the same logic as `POST /firmware/flash`, records audit events, and restarts the service automatically after successful apply.

The GUI is fully migrated to this package-update flow. There is no dual GUI path and no fallback UX for firmware-only actions. The only remaining firmware-only behavior is the existing API endpoint `POST /firmware/flash`, which stays available and is internally reused by the package-update endpoint.

A separate standalone ZIP Generator GUI tool is also delivered to build valid update packages with minimal manual editing.

## Progress

- [x] (2026-02-13 00:00Z) Captured product direction: async updates, all-box scope, lock + audit, auto restart.
- [x] (2026-02-13 00:10Z) Confirmed constraints: no signature verification, no dry-run, no compatibility matrix, partial packages allowed.
- [x] (2026-02-13 00:20Z) Confirmed GUI migration rule: single update-package UX, no fallback track.
- [x] (2026-02-13 05:40Z) Implemented package contract + validation module (rest_api/update_package.py) with typed manifest parsing, checksum/path safety checks, and component model enforcement.
- [x] (2026-02-13 05:55Z) Implemented async REST endpoints and in-memory update orchestration (POST /updates/package, GET /updates/{update_id}, GET /updates) with lock, audit log, ordered apply, and restart result capture.
- [x] (2026-02-13 06:00Z) Refactored firmware flashing into shared helper in rest_api/app.py and wired both POST /firmware/flash and package-update worker to it.
- [x] (2026-02-13 06:12Z) Migrated GUI Settings to package-update-only controls and added strict modal progress popup (seva/app/views/update_progress_dialog.py) with backend step + heartbeat polling.
- [x] (2026-02-13 06:15Z) Removed legacy GUI firmware-only wiring (controller callbacks, settings view-model field, and settings dialog controls).
- [x] (2026-02-13 06:20Z) Added standalone ZIP Generator GUI (StreamingStandalone/update_zip_generator.py) for full or partial package creation.
- [x] (2026-02-13 06:28Z) Added contract-driven tests for UseCase↔Adapter and REST boundary (`seva/tests/test_remote_update_usecases.py`, `rest_api/tests/test_update_endpoints.py`).
- [x] (2026-02-13 06:34Z) Updated /docs for REST workflow, SEVA workflow, class/module maps, and operator GUI usage.
- [x] (2026-02-13 06:36Z) Ran validation (py -3.13 -m pytest -q) and manual curl start/poll verification; captured evidence snippets below.

## Surprises & Discoveries

- Observation: Firmware flashing is already implemented end-to-end with upload validation, script execution, and typed HTTP error payloads.
  Evidence: rest_api/app.py route POST /firmware/flash includes validation, storage, subprocess call, and structured errors.

- Observation: Current GUI follows MVVM + Hexagonal layering for settings actions and firmware use case calls.
  Evidence: existing flow is View -> UseCase -> Adapter -> API, so package-update can be added without breaking architecture boundaries.

- Observation: Local Python 3.13 validation environment does not include serial/pyBEEP, so REST boundary tests and manual validation required startup stubs.
  Evidence: rest_api/tests/test_update_endpoints.py and .tmp_validation/validation_server.py inject serial and pyBEEP stubs before importing rest_api/app.py.

- Observation: First manual curl upload failed due malformed checksum sample generation (\\n literal in checksum line), not backend logic.
  Evidence: API returned updates.checksum_missing; regenerated sample ZIP succeeded with terminal status=done.

## Decision Log

- Decision: Package updates are always scoped to all boxes; manifest does not include per-box targets.
  Rationale: Product requirement is global rollout per update action.
  Date/Author: 2026-02-13 / Codex.

- Decision: Partial packages are valid.
  Rationale: If a package includes only firmware + pyBEEP, only those components are applied.
  Date/Author: 2026-02-13 / Codex.

- Decision: Keep POST /firmware/flash as public API and reuse its core implementation in package flow.
  Rationale: No legacy removal at API contract level; strict DRY implementation for flashing behavior.
  Date/Author: 2026-02-13 / Codex.

- Decision: GUI is fully migrated to package update only; no firmware-only button in GUI.
  Rationale: Product requests one clear UX path and avoids parallel UI tracks.
  Date/Author: 2026-02-13 / Codex.

- Decision: Update status UX uses a strict modal popup with explicit “still running” heartbeat.
  Rationale: Prevent user perception of frozen process while long-running async tasks execute.
  Date/Author: 2026-02-13 / Codex.

- Decision: KISS/YAGNI scope excludes signature check, dry-run, compatibility matrix, and rollback framework.
  Rationale: Keep v1 minimal and operationally clear.
  Date/Author: 2026-02-13 / Codex.

- Decision: Implement package-update worker as dedicated module rest_api/update_package.py with typed update exceptions.
  Rationale: Keeps route handlers focused on HTTP concerns and makes validation/apply logic testable in isolation.
  Date/Author: 2026-02-13 / Codex.

- Decision: Service restart command is configurable via BOX_RESTART_COMMAND and defaults to systemctl restart seva-rest-api.service.
  Rationale: Supports deployment-specific service names while preserving automatic restart behavior.
  Date/Author: 2026-02-13 / Codex.

- Decision: GUI polling loop uses backend snapshots as source of truth and blocks conflicting actions with strict modal grab.
  Rationale: Aligns with architecture guardrails and the explicit non-frozen UX requirement.
  Date/Author: 2026-02-13 / Codex.

## Outcomes & Retrospective

Implemented outcome:

- Backend now supports validated async package updates with lock/audit/restart and server-authoritative status polling.
- POST /firmware/flash and package-worker firmware step share the same flashing core helper in rest_api/app.py.
- GUI Settings is fully migrated to package-update-only flow with strict modal progress dialog and heartbeat updates.
- Standalone ZIP generator GUI is available at StreamingStandalone/update_zip_generator.py.
- New tests cover use-case contracts and REST endpoint boundary behavior; full suite passes on Python 3.13.

Gaps and residual risk:

- Automatic restart command behavior depends on deployment service naming (BOX_RESTART_COMMAND) and host process privileges.
- GUI screenshot evidence is not embedded here because this execution environment is headless.

## Context and Orientation

### Existing system context

- REST API entrypoint: `rest_api/app.py`.
- Existing firmware-only endpoint: `POST /firmware/flash`.
- Existing GUI Settings dialog currently exposes firmware-only controls and must be replaced.
- Existing architecture requirement: Views render only, UseCases orchestrate, Adapters perform I/O.
- pyBEEP offline editable install is documented as `-e ./vendor/pyBEEP`, and `vendor/` is located next to `rest_api/` in the repository tree.

### Terms used in this plan

- Async update: `POST` returns quickly with `update_id`; client polls `GET` status endpoint.
- Concurrency lock: only one active update operation at a time on the service.
- Audit log: append-only event log with timestamps and step outcomes.
- `archive_path` in `manifest.json`: relative file path inside the ZIP to a component archive file, e.g. `rest_api/rest_api_bundle.tar.gz`.
- Vendor root derivation: resolve repository root from `rest_api/app.py` location (`Path(__file__).resolve().parent.parent`), then derive pyBEEP target path as `<repo_root>/vendor/pyBEEP`.

### pyBEEP apply target rule (explicit)

When the deployed API environment uses editable vendor installation (`-e ./vendor/pyBEEP`), the update worker must write pyBEEP updates into the vendor source directory at `<repo_root>/vendor/pyBEEP`.

The target path must be derived from the REST API file location (repo root) rather than hardcoded absolute host paths, so the update remains portable across Raspberry Pi deployments.

This is now a required behavior for implementation and validation.

## Package contract (v1)

The package has a fixed top-level structure with optional component folders:

    update-package.zip
      manifest.json
      checksums.sha256
      rest_api/
        rest_api_bundle.tar.gz
      pybeep/
        pybeep_bundle.tar.gz
      firmware/
        controller.bin

`manifest.json` example:

    {
      "schema_version": "1.0",
      "package_id": "update-2026-02-13-001",
      "created_at_utc": "2026-02-13T12:00:00Z",
      "created_by": "zip-generator-gui",
      "components": {
        "rest_api": {
          "version": "1.2.0",
          "archive_path": "rest_api/rest_api_bundle.tar.gz",
          "sha256": "<sha256>"
        },
        "pybeep": {
          "version": "0.9.4",
          "archive_path": "pybeep/pybeep_bundle.tar.gz",
          "sha256": "<sha256>"
        },
        "firmware": {
          "version": "3.4.1",
          "bin_path": "firmware/controller.bin",
          "sha256": "<sha256>",
          "flash_mode": "reuse_firmware_endpoint_logic"
        }
      }
    }

Rules:

- No `targets` field.
- Any subset of `components` is allowed.
- Checksums must match the referenced files.
- Paths are ZIP-internal relative paths only.

## Plan of Work

### Milestone 1: Implement package models and validation

Create typed models for manifest and job status in REST API code. Validate package structure, path safety, and checksums. Reject malformed packages with existing API error shape (`code`, `message`, `hint`).

Acceptance: valid full and partial packages pass; invalid packages fail with deterministic error codes.

### Milestone 2: Add async update API endpoints

Add `POST /updates/package` to upload and enqueue an update job. Add `GET /updates/{update_id}` to poll state. Optionally add `GET /updates` for recent jobs.

Acceptance: GUI receives `update_id` quickly and can poll until terminal state.

### Milestone 3: Orchestrate component apply with lock + audit

Implement background worker with ordered apply (`pybeep`, `rest_api`, `firmware` when present), service-wide lock, timeout handling, and audit writes.

For `pybeep`, apply into `<repo_root>/vendor/pyBEEP` when editable vendor mode is used.

Acceptance: parallel update requests are rejected while one job is active; audit log shows start, component steps, terminal result.

### Milestone 4: Reuse firmware endpoint logic in package flow

Refactor shared flashing behavior into one helper callable used by:

- existing `POST /firmware/flash`
- package-worker firmware step

Do not keep duplicated flashing implementation.

Acceptance: same script call, validation semantics, and error mapping for both paths.

### Milestone 5: Auto restart on successful apply

After successful component apply, perform automatic service restart and report restart result in job status and audit. Keep implementation simple and retry-safe.

Acceptance: successful jobs include restart success event and service comes back with updated versions.

### Milestone 6: GUI migration to update-package only + modal progress

Replace firmware-only settings controls with update-package controls. Add strict modal progress popup with spinner, current backend step, last heartbeat timestamp, and explicit non-frozen message.

The modal remains open until terminal state and blocks conflicting actions.

Acceptance: operator clearly sees â€œrunningâ€ progress and never receives a frozen-looking static screen.

### Milestone 7: Standalone ZIP Generator GUI tool

Create a separate script/app that allows operators to:

- input manifest metadata fields,
- pick REST API folder,
- pick pyBEEP folder,
- pick firmware `.bin`,
- choose output ZIP path,
- generate valid package (including `manifest.json` + checksums).

No MVVM/Hexagonal constraints are required for this standalone utility.

Acceptance: generated ZIP is accepted by `POST /updates/package` for full and partial component sets.

### Milestone 8: Tests and documentation

Add contract-driven tests for REST payloads and UseCaseâ†”Adapter interactions. Keep UI tests minimal. Update docs in `/docs` for new workflow and endpoint contract.

Acceptance: test suite passes; docs match implemented behavior and operator flow.

## Concrete Steps

Working directory: /workspace/SEVA_GUI_MVVM.

1. Baseline and branch state.

    git status

2. Implement REST package models, validation, endpoints, and worker.

3. Extract shared flash helper and wire both endpoints.

4. Implement GUI migration + strict modal polling popup.

5. Implement standalone ZIP Generator GUI script.

6. Add/update tests.

    py -3.13 -m pytest -q

7. Manual API verification (local API running).

    curl -X POST http://127.0.0.1:8000/updates/package -F "file=@sample-update.zip"

    curl http://127.0.0.1:8000/updates/<update_id>

Execution record:

    py -3.13 -m pytest -q
    14 passed in 1.68s

    curl -X POST http://127.0.0.1:8000/updates/package -F "file=@sample-update.zip"
    {"update_id":"fc23ac1e427441bb9873ce35b604dab5","status":"running","step":"validate_package","queued_at":"2026-02-13T06:34:20Z"}

    curl http://127.0.0.1:8000/updates/fc23ac1e427441bb9873ce35b604dab5
    {"update_id":"fc23ac1e427441bb9873ce35b604dab5","status":"done","step":"done","components":{"pybeep":"skipped","rest_api":"skipped","firmware":"done"},"restart":{"ok":true,"exit_code":0,"stdout":"","stderr":""}}

## Validation and Acceptance

The feature is accepted when all items are true:

1. Uploading a valid package returns `update_id` quickly.
2. Polling returns server-authoritative progress states until terminal status.
3. Full and partial packages apply only included components.
4. Concurrency lock prevents concurrent update jobs.
5. Audit log records all major lifecycle events.
6. Firmware flashing inside package flow uses same core logic as `POST /firmware/flash`.
7. Service restarts automatically after successful apply.
8. GUI offers only package-update flow, with strict modal live progress.
9. Standalone ZIP Generator can produce packages accepted by API.

## Idempotence and Recovery

- Validation and staging are repeatable.
- Failed jobs can be retried with corrected package.
- No rollback framework in v1; recovery is re-apply a known good package.
- Lock is always released at terminal status.

## Artifacts and Notes

Collect these implementation artifacts:

- sample manifest.json and checksum file,
- sample audit log excerpt,
- curl start/poll transcript,
- GUI screenshot of modal progress,
- test output snippet for new contract tests.

Collected evidence snippets:

    py -3.13 -m pytest -q seva/tests/test_remote_update_usecases.py rest_api/tests/test_update_endpoints.py
    ......                                                                   [100%]
    6 passed in 1.57s

    py -3.13 -m pytest -q
    ..............                                                           [100%]
    14 passed in 1.68s

    curl -X POST http://127.0.0.1:8000/updates/package -F "file=@sample-update.zip"
    {"update_id":"fc23ac1e427441bb9873ce35b604dab5","status":"running","step":"validate_package","queued_at":"2026-02-13T06:34:20Z"}

    curl http://127.0.0.1:8000/updates/fc23ac1e427441bb9873ce35b604dab5
    {"update_id":"fc23ac1e427441bb9873ce35b604dab5","status":"done","step":"done","components":{"pybeep":"skipped","rest_api":"skipped","firmware":"done"},"restart":{"ok":true,"exit_code":0,"stdout":"","stderr":""}}

## Interfaces and Dependencies

REST endpoints:

- keep `POST /firmware/flash`.
- add `POST /updates/package`.
- add `GET /updates/{update_id}`.
- optional `GET /updates`.

Suggested v1 operational limits:

- ZIP max size: 500 MB.
- upload request timeout: 120s.
- poll timeout: 10s.
- poll interval: 1-2s.
- per-box apply timeout: 10 min.
- whole-job timeout: 30 min.

---

Plan revision notes:

- 2026-02-13: rewritten in English and aligned with clarified product constraints (no manifest targets, strict modal popup, partial packages, full GUI migration, standalone ZIP generator, and shared firmware logic).
- 2026-02-13: implemented milestones 1-8, updated living sections with execution evidence, and documented final behavior/tests.





