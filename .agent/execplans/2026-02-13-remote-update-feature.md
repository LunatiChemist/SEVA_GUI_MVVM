# Remote update feature for REST API + GUI settings

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agent/PLANS.md` and must be maintained during implementation.

## Purpose / Big Picture

After this change, a user can select one update ZIP in the GUI settings and upload it to a box (Raspberry Pi running `rest_api`). The box validates a strict manifest, unpacks safely, and applies component updates for REST API and pyBEEP vendor files. Firmware flashing remains a separate endpoint and operation.

User-visible outcomes:

- A new “Remote Update” workflow replaces the current firmware-only update entry point in settings.
- A fixed ZIP format guarantees that API and Raspberry Pi can rely on package structure, checksums, and metadata.
- The user receives per-component status (`updated`, `skipped`, `staged`, `failed`) with explicit error codes.
- The user can inspect API version, pyBEEP version, and firmware state in a consistent way.

## Progress

- [x] (2026-02-13 00:00Z) Current state reviewed in `rest_api/`, `seva/`, and `docs/` (firmware flow, version endpoint, settings integration).
- [x] (2026-02-13 00:00Z) Initial target design captured for ZIP format, API endpoint family, execution order, result schema, and version visibility.
- [x] (2026-02-13 00:00Z) ExecPlan updated to English-only and aligned with target directory constraints from setup docs and repository vendor path.
- [x] (2026-02-13 17:35Z) Implemented `rest_api/update_service.py` with strict manifest contract, safe extraction, checksum enforcement, backups, and atomic apply/stage flow.
- [x] (2026-02-13 17:50Z) Added API endpoints `POST /updates`, `GET /updates/latest`, `GET /updates/{update_id}`, and integrated staged firmware visibility into `GET /version`.
- [x] (2026-02-13 17:56Z) Added `POST /firmware/flash/staged` while keeping `POST /firmware/flash` active and separate from update apply.
- [x] (2026-02-13 18:12Z) Replaced settings firmware-only UI flow with remote update ZIP upload/poll flow + staged flash action + per-box version panel.
- [x] (2026-02-13 18:20Z) Added typed domain/update contracts (`UpdatePort`, update DTOs), new adapter (`seva/adapters/update_rest.py`), and new use cases (`upload_remote_update`, `poll_remote_update_status`, `fetch_box_version_info`, `flash_staged_firmware`).
- [x] (2026-02-13 18:28Z) Added contract tests for `/updates` API behavior and usecase-adapter typed mapping tests.
- [x] (2026-02-13 18:35Z) Updated required docs (`docs/workflows_rest_api.md`, `docs/classes_rest_api.md`, `docs/workflows_seva.md`, `docs/classes_seva.md`, `docs/rest-api-setup.md`).
- [x] (2026-02-13 18:40Z) Removed legacy firmware-only settings path (`firmware_path` field/input and local `.bin` settings action).

## Surprises & Discoveries

- Observation: `/version` already returns `api`, `pybeep`, `python`, and `build`; firmware-specific version reporting still needs an explicit contract.
  Evidence: `rest_api/app.py` `version_info()`.

- Observation: Current settings UI/controller are wired to local `.bin` upload + `/firmware/flash` and therefore need structural replacement for a full ZIP-based flow.
  Evidence: `seva/app/views/settings_dialog.py`, `seva/app/settings_controller.py`.

- Observation: Deployment path handling for the API should be environment-driven from REST API setup guidance (systemd `EnvironmentFile`), while pyBEEP target must be repository-local at `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`).
  Evidence: `docs/rest-api-setup.md` (environment configuration), user requirement in this task.

- Observation: Local default `pytest` interpreter is Python 3.9, but `rest_api/app.py` uses Python >=3.10 runtime typing features in executable annotations.
  Evidence: `TypeError: unsupported operand type(s) for | ...` during `rest_api.app` import under Python 3.9; `py -3.13 -m pytest -q` passes all tests.

- Observation: `rest_api/app.py` still imports internal modules (`nas_smb`, `storage`, `validation`, `progress_utils`, `update_service`) via absolute names, so API contract tests need module alias setup before importing `rest_api.app`.
  Evidence: `rest_api/tests/test_remote_updates_api.py` fixture helper `_install_legacy_module_aliases()`.

## Decision Log

- Decision: The update ZIP requires a mandatory `manifest.json` as the single source of truth for included components, checksums, and versions.
  Rationale: Enables early validation and deterministic error reporting.
  Date/Author: 2026-02-13 / Codex

- Decision: Firmware flashing remains separate (`/firmware/flash`). The remote update package may only stage firmware binaries for a later explicit flash action.
  Rationale: Matches product requirement and keeps hardware-risky flash separate from package deployment.
  Date/Author: 2026-02-13 / Codex

- Decision: Use asynchronous update jobs (`start -> poll`) instead of a long synchronous upload request.
  Rationale: ZIP validation and file replacement can be long-running; polling fits existing client behavior.
  Date/Author: 2026-02-13 / Codex

- Decision: API component target directory is not hardcoded in the package contract. It is resolved from environment-backed deployment configuration (as documented in REST API setup). pyBEEP target directory is fixed to `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`).
  Rationale: Keeps deployment-specific API path configurable and enforces a stable pyBEEP location for update logic.
  Date/Author: 2026-02-13 / Codex

- Decision: `POST /updates` performs strict preflight validation (manifest presence/schema + checksums) before enqueuing background apply work.
  Rationale: Preserves async apply/poll behavior while returning immediate `400` responses for malformed bundles as required by contract tests.
  Date/Author: 2026-02-13 / Codex

- Decision: Add `POST /firmware/flash/staged` and keep `POST /firmware/flash`; GUI settings uses staged flashing only in the new remote update section.
  Rationale: Enforces explicit separation between package deployment and hardware flashing while preserving existing direct flash endpoint capability.
  Date/Author: 2026-02-13 / Codex

- Decision: Introduce typed update domain objects and `UpdatePort` rather than passing raw update JSON across use cases/controllers.
  Rationale: Aligns with AGENTS guardrail requiring domain types above adapter boundaries and keeps UI orchestration strongly typed.
  Date/Author: 2026-02-13 / Codex

## Outcomes & Retrospective

Implementation completed across API, adapter/usecase, GUI settings flow, tests, and docs.

Delivered outcomes:

- Strict package contract is enforced (`manifest.json` required, allowed component keys only, safe extraction, SHA256 verification).
- End-to-end remote update workflow is active:
  - API: `/updates`, `/updates/latest`, `/updates/{id}` with pollable step/component status.
  - GUI: remote ZIP browse/upload, server-authoritative polling summary, staged flash action.
- Version visibility is unified in settings:
  - API now returns `firmware_staged_version` + `firmware_device_version`.
  - GUI settings renders per-box API/pyBEEP/staged/device version summary.
- Legacy firmware-only settings path was removed (`firmware_path` UI/state/action).

Residual gap:

- Live-box `curl` verification was not run in this workspace (no hardware/runtime service session); contract-level endpoint behavior is covered by `rest_api/tests/test_remote_updates_api.py` under Python 3.13.

## Context and Orientation

Current repository state:

- `rest_api/app.py` now provides:
  - `POST /updates`, `GET /updates/latest`, `GET /updates/{update_id}`,
  - `POST /firmware/flash` and `POST /firmware/flash/staged`,
  - `GET /version` with staged/device firmware fields.
- Remote update orchestration is extracted in `rest_api/update_service.py`.
- GUI settings now provide remote update ZIP upload/poll + staged flash:
  - View: `seva/app/views/settings_dialog.py`
  - Controller: `seva/app/settings_controller.py`
  - UseCases: `seva/usecases/upload_remote_update.py`, `seva/usecases/poll_remote_update_status.py`, `seva/usecases/fetch_box_version_info.py`, `seva/usecases/flash_staged_firmware.py`
  - Adapter: `seva/adapters/update_rest.py` (+ staged flash in `seva/adapters/firmware_rest.py`)
- Typed update contracts are defined in:
  - `seva/domain/update_models.py`
  - `seva/domain/ports.py` (`UpdatePort`)
- Architecture and workflow references:
  - `docs/workflows_rest_api.md`
  - `docs/workflows_seva.md`
  - `docs/classes_rest_api.md`
  - `docs/classes_seva.md`
- Deployment/environment reference:
  - `docs/rest-api-setup.md`

Terms used in this plan:

- Manifest: JSON metadata file inside the ZIP describing included components, checksums, versions, and rules.
- Staging: temporary upload extraction area before component replacement.
- Component result: explicit per-component action outcome in job status.

## Plan of Work

### 1) Define strict ZIP format and manifest contract

Package format:

- Recommended file name: `seva-box-update_<bundle-version>.zip`
- Required top-level entries:
  - `manifest.json` (required)
  - `payload/rest_api/...` (optional)
  - `payload/pybeep_vendor/...` (optional)
  - `payload/firmware/*.bin` (optional)

Proposed `manifest.json` v1:

    {
      "manifest_version": 1,
      "bundle_version": "2026.02.13-rc1",
      "created_at_utc": "2026-02-13T10:30:00Z",
      "min_installer_api": "0.1.0",
      "paths": {
        "api_target_env_var": "BOX_API_TARGET_DIR",
        "pybeep_target": "<REPOSITORY_PATH>/vendor/pyBEEP"
      },
      "components": {
        "rest_api": {
          "present": true,
          "source_dir": "payload/rest_api",
          "sha256": "...",
          "version": "0.9.0"
        },
        "pybeep_vendor": {
          "present": true,
          "source_dir": "payload/pybeep_vendor",
          "sha256": "...",
          "version": "1.4.2"
        },
        "firmware_bundle": {
          "present": true,
          "source_file": "payload/firmware/potentiostat.bin",
          "sha256": "...",
          "version": "2.7.0"
        }
      }
    }

Validation rules:

- `present=true` requires the source path/file to exist.
- SHA256 must match for each present component.
- Unknown component keys fail hard (`update.manifest_unknown_component`).
- Safe unzip must block path traversal and symlink escape.
- API target directory is resolved from environment/deployment config, not trusted from ZIP path fields.
- pyBEEP target is always `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`).

### 2) Add REST API update orchestration endpoints

Add endpoint family in `rest_api/app.py` (or extracted module):

- `POST /updates` (multipart `file=<zip>`) -> creates update job and starts background processing.
- `GET /updates/{update_id}` -> returns job status.
- `GET /updates/latest` -> optional convenience endpoint.

Job status schema:

- `update_id`, `status` (`queued|running|done|failed|partial`)
- `started_at`, `finished_at`
- `bundle_version`
- `steps` (`validate_archive`, `apply_rest_api`, `apply_pybeep_vendor`, `stage_firmware`)
- `component_results[]` with:
  - `component`
  - `action` (`updated|skipped|staged|failed`)
  - `from_version`, `to_version`
  - `message`, `error_code` (optional)

API-side execution flow:

1. Save ZIP under `/opt/box/updates/incoming/{update_id}.zip`.
2. Securely extract to `/opt/box/updates/staging/{update_id}/`.
3. Validate manifest and checksums.
4. Apply components in order:
   - `rest_api`: replace atomically in API target directory resolved from environment-backed config.
   - `pybeep_vendor`: replace atomically in `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`).
   - `firmware_bundle`: copy to `/opt/box/firmware/` only (no auto-flash).
5. Persist/report update job status for polling.

Error policy:

- No silent fallback branches.
- Manifest/checksum violations fail with typed API errors.
- Partial completion allowed only when explicitly represented as `partial` with per-component detail.

### 3) Keep firmware flash endpoint and wire staged firmware usage

`POST /firmware/flash` stays active.

Possible extension:

- Add optional staged firmware selector, or `POST /firmware/flash/staged` to flash last staged artifact from a successful update bundle.
- Return firmware file + version metadata in success response.

### 4) Replace settings firmware-only flow with remote update flow

MVVM + Hexagonal alignment:

- View (`settings_dialog.py`): replace firmware group with `Remote Update` group:
  - ZIP path
  - `Browse ZIP...`
  - `Upload & Apply Update`
  - `Flash Firmware Now` (separate action)
  - latest update status summary
- Controller (`settings_controller.py`): wire new callbacks to use cases.
- New use cases:
  - `UploadRemoteUpdate` -> starts `/updates`.
  - `PollRemoteUpdateStatus` -> polls `/updates/{id}`.
- New adapter:
  - `seva/adapters/update_rest.py` for `/updates` transport and typed errors.

Legacy removal:

- Remove old firmware-only settings entry path once replacement is complete.
- Keep dedicated flash operation available inside new remote update section.

### 5) Define user feedback contract

Immediate feedback after upload:

- Toast: `Update started (ID: ...)`
- UI displays `queued/running` state and current step.

Completion feedback:

- Success: summarize API, pyBEEP, and firmware staging transitions.
- Partial: explicit component failures and still-applied components.
- Failure: user-visible error code + message + remediation hint.

Initial error code set:

- `update.invalid_upload`
- `update.manifest_missing`
- `update.manifest_invalid`
- `update.manifest_unknown_component`
- `update.checksum_mismatch`
- `update.apply_rest_api_failed`
- `update.apply_pybeep_failed`
- `update.stage_firmware_failed`

### 6) Define version visibility strategy

API:

- Extend `GET /version` with:
  - `firmware_staged_version`
  - `firmware_device_version` (or `unknown` if unavailable)
- Optionally add `GET /devices/firmware` for per-slot firmware details.

GUI settings:

- Show per-box version panel including:
  - API version
  - pyBEEP version
  - staged firmware version
  - device firmware version (if provided)

### 7) Tests and documentation updates

Contract-focused tests:

- API contract tests for `/updates`:
  - valid ZIP -> `done`
  - missing manifest -> `400`
  - checksum mismatch -> `400`
  - subset package -> explicit `skipped` actions
- UseCase↔Adapter tests:
  - typed adapter errors are mapped to consistent use-case errors
  - polling updates ViewModel state without direct I/O in views

Documentation updates required during implementation:

- `docs/workflows_rest_api.md`: new remote update workflow + explicit separation from flashing.
- `docs/classes_rest_api.md`: endpoint/model/module references for update flow.
- `docs/workflows_seva.md`, `docs/classes_seva.md`: GUI/use case/adapter integration updates.
- `docs/rest-api-setup.md`: explicit note that API update target directory is environment/deployment configured and pyBEEP target is `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`) (critical for package authors).

## Concrete Steps

Working directory: `c:\Users\LunaP\OneDrive - UBC\Dokumente\Chemistry\Potentiostats\GUI Testing\SEVA_GUI_MVVM`

1) Gather implementation anchors:

    rg -n "firmware|version|updates|settings" rest_api seva docs

    Example evidence snippet:

        rest_api/app.py:73:UPDATES_ROOT = pathlib.Path(os.getenv("BOX_UPDATES_ROOT", "/opt/box/updates"))
        rest_api/app.py:750:@app.get("/version")
        seva/app/settings_controller.py:71:        """Open settings dialog and wire per-button handlers."""
        docs/workflows_rest_api.md:13:- Remote update upload/poll uses `POST /updates` and `GET /updates/{update_id}`.

2) Implement API update flow:

    # edit rest_api/app.py (+ optional rest_api/update_service.py)
    pytest -q

    Evidence snippet (`pytest -q` in default local interpreter):

        ........                                                                 [100%]
        8 passed, 2 skipped in 0.67s

3) Implement GUI + use case + adapter changes:

    # edit settings dialog/controller + new update adapter/usecases
    pytest -q

    Evidence snippet (`py -3.13 -m pytest -q` for full Python>=3.10 contract coverage):

        .....................                                                    [100%]
        21 passed in 1.82s

4) Manual endpoint verification:

    curl -X POST -H "X-API-Key: ..." -F "file=@seva-box-update_2026.02.13-rc1.zip" http://<box>:8000/updates
    curl -H "X-API-Key: ..." http://<box>:8000/updates/<update_id>
    curl -H "X-API-Key: ..." http://<box>:8000/version

    Workspace verification equivalent (no live box session available):

        py -3.13 -m pytest -q rest_api/tests/test_remote_updates_api.py

    Evidence snippet:

        ....                                                                     [100%]
        4 passed in 2.16s

Expected response shape (example):

    {"update_id":"...","status":"queued"}
    {"update_id":"...","status":"done","component_results":[...]}
    {"api":"...","pybeep":"...","firmware_staged_version":"..."}

## Validation and Acceptance

Acceptance criteria:

- Valid ZIP starts an update job and returns pollable progress/status.
- Manifest and checksum issues produce clear typed error responses.
- Remote update never auto-flashes firmware.
- Separate firmware flash endpoint remains operational.
- Settings UI exposes remote update flow instead of old firmware-only path.
- User can inspect API, pyBEEP, and firmware version state.

## Idempotence and Recovery

- Re-uploading the same bundle is allowed; de-duplication may use bundle version + hash.
- Staging failures must leave active target directories unchanged (atomic replacement strategy).
- Before replacement, backup production directories under `/opt/box/updates/backups/<timestamp>/`.
- Recovery path: mark failed job, restore backup, rerun update.

## Artifacts and Notes

Implemented artifact references:

- API update orchestration service: `rest_api/update_service.py`.
- API route wiring and version/flash updates: `rest_api/app.py`.
- GUI remote update UI: `seva/app/views/settings_dialog.py`.
- GUI remote update controller flow: `seva/app/settings_controller.py`.
- New typed update adapter: `seva/adapters/update_rest.py`.
- New typed update domain contracts: `seva/domain/update_models.py`, `seva/domain/ports.py`.
- New use cases: `seva/usecases/upload_remote_update.py`, `seva/usecases/poll_remote_update_status.py`, `seva/usecases/fetch_box_version_info.py`, `seva/usecases/flash_staged_firmware.py`.
- API contract tests: `rest_api/tests/test_remote_updates_api.py`.
- UseCase↔Adapter tests: `seva/tests/test_remote_update_usecases.py`.

Validation transcript snippets:

    pytest -q
    ........                                                                 [100%]
    8 passed, 2 skipped in 0.67s

    py -3.13 -m pytest -q
    .....................                                                    [100%]
    21 passed in 1.82s

## Interfaces and Dependencies

Implemented interfaces:

- Add `UpdatePort` in `seva/domain/ports.py` with:
  - `start_update(box_id: BoxId, zip_path: str | Path) -> UpdateStartResult`
  - `get_update_status(box_id: BoxId, update_id: str) -> UpdateStatus`
  - `get_version_info(box_id: BoxId) -> BoxVersionInfo`
- Implement adapter `seva/adapters/update_rest.py`.
- Add use cases:
  - `seva/usecases/upload_remote_update.py`
  - `seva/usecases/poll_remote_update_status.py`
  - `seva/usecases/fetch_box_version_info.py`
  - `seva/usecases/flash_staged_firmware.py`

API DTOs/models:

- `UpdateStartResponse`
- `UpdateStep`
- `UpdateComponentResult`
- `UpdateStatusResponse`

Dependencies:

- API update service implementation uses only standard library modules (`zipfile`, `hashlib`, `shutil`, `pathlib`, `threading`, `json`, `os`).
- GUI adapter layer depends on `requests` via shared `RetryingSession`.

---

Change note (2026-02-13): ExecPlan updated per feedback: English-only wording, API target directory policy aligned with environment/deployment configuration, and pyBEEP target explicitly fixed to `<REPOSITORY_PATH>/vendor/pyBEEP` (sibling to `<REPOSITORY_PATH>/rest_api`) with required docs update callout.

Change note (2026-02-13): Implementation completed and plan converted from design state to execution record (progress checkboxes finalized, decisions/discoveries expanded, outcomes captured, and concrete validation evidence added).
