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
- [ ] Define and implement package contract (`manifest.json`, checksums, folder layout).
- [ ] Implement async REST orchestration endpoints and in-memory job state.
- [ ] Reuse existing firmware flash endpoint logic from package flow.
- [ ] Add strict modal “update running” popup with heartbeat/progress in GUI.
- [ ] Remove legacy GUI firmware-only controls and related wiring.
- [ ] Build standalone ZIP Generator GUI script.
- [ ] Add contract-driven tests at UseCase↔Adapter and REST boundary.
- [ ] Update docs for REST/API workflow and operator usage.
- [ ] Run validation, collect evidence, and finalize retrospective.

## Surprises & Discoveries

- Observation: Firmware flashing is already implemented end-to-end with upload validation, script execution, and typed HTTP error payloads.
  Evidence: `rest_api/app.py` route `POST /firmware/flash` includes validation, storage, subprocess call, and structured errors.

- Observation: Current GUI follows MVVM + Hexagonal layering for settings actions and firmware use case calls.
  Evidence: existing flow is View -> UseCase -> Adapter -> API, so package-update can be added without breaking architecture boundaries.

## Decision Log

- Decision: Package updates are always scoped to all boxes; manifest does not include per-box targets.
  Rationale: Product requirement is global rollout per update action.
  Date/Author: 2026-02-13 / Codex.

- Decision: Partial packages are valid.
  Rationale: If a package includes only firmware + pyBEEP, only those components are applied.
  Date/Author: 2026-02-13 / Codex.

- Decision: Keep `POST /firmware/flash` as public API and reuse its core implementation in package flow.
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

## Outcomes & Retrospective

Current state: planning refined and aligned with clarified requirements.

Definition of done for this initiative:

- One package-update UX in GUI with modal live status.
- Async backend update endpoints with lock, audit, and restart.
- Shared firmware flashing implementation between package-update and firmware-only API endpoint.
- Standalone ZIP Generator GUI can create valid full or partial packages.

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

Acceptance: operator clearly sees “running” progress and never receives a frozen-looking static screen.

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

Add contract-driven tests for REST payloads and UseCase↔Adapter interactions. Keep UI tests minimal. Update docs in `/docs` for new workflow and endpoint contract.

Acceptance: test suite passes; docs match implemented behavior and operator flow.

## Concrete Steps

Working directory: `/workspace/SEVA_GUI_MVVM`.

1. Baseline and branch state.

    git status

2. Implement REST package models, validation, endpoints, and worker.

3. Extract shared flash helper and wire both endpoints.

4. Implement GUI migration + strict modal polling popup.

5. Implement standalone ZIP Generator GUI script.

6. Add/update tests.

    pytest -q

7. Manual API verification (local API running).

    curl -X POST http://localhost:8000/updates/package \
      -H "X-API-Key: <key>" \
      -F "file=@sample-update.zip"

    curl -H "X-API-Key: <key>" \
      http://localhost:8000/updates/<update_id>

Expected progression example:

    {"update_id":"...","status":"queued"}
    {"update_id":"...","status":"running","step":"apply_pybeep"}
    {"update_id":"...","status":"running","step":"flash_firmware"}
    {"update_id":"...","status":"done","restart":{"ok":true}}

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

- sample `manifest.json` and checksum file,
- sample audit log excerpt,
- curl start/poll transcript,
- GUI screenshot of modal progress,
- test output snippet for new contract tests.

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
