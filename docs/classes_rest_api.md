# REST API Classes and Modules

This document maps FastAPI modules in `rest_api/` to their runtime roles.

## Scope

- API routes and request/response models (`rest_api/app.py`)
- Payload validation (`rest_api/validation.py`)
- Progress utilities (`rest_api/progress_utils.py`)
- Storage mapping (`rest_api/storage.py`)
- NAS/SMB upload managers (`rest_api/nas.py`, `rest_api/nas_smb.py`)

## `rest_api/app.py`

Entry module for the FastAPI server. It hosts:

- HTTP endpoints used by GUI adapters in `seva/adapters/*`
- request/response schemas (`DeviceInfo`, `JobRequest`, `JobStatus`, etc.)
- in-memory runtime registries (`DEVICES`, `JOBS`, `SLOT_RUNS`, `CANCEL_FLAGS`)
- worker-thread orchestration for slot-level execution
- artifact serving (`/runs/{run_id}/files`, `/runs/{run_id}/file`, `/runs/{run_id}/zip`)
- NAS trigger endpoints (`/nas/*`, `/runs/{run_id}/upload`)

Key class contracts:

- `DeviceInfo`: normalized hardware metadata per slot
- `JobRequest`: start payload for multi-device, multi-mode runs
- `SlotStatus`: slot-local progress and terminal status
- `JobStatus`: run-level aggregate state and progress
- `JobOverview`: compact projection for list views
- `JobStatusBulkRequest`: batch status lookup request body
- `SMBSetupRequest`: NAS/SMB configuration payload
- `TemperatureSample` / `LatestResponse`: telemetry payload models

## `rest_api/validation.py`

Parameter validation engine used by `/modes/{mode}/validate`.

- Defines `ValidationIssue` and `ValidationResult` as machine-readable output.
- Collects errors and warnings without contacting hardware.
- Throws `UnsupportedModeError` for unsupported modes.

The GUI uses this endpoint to fail fast before `/jobs` submission.

## `rest_api/progress_utils.py`

Pure helper module for run progress and ETA calculations.

- `estimate_planned_duration(mode, params)`: mode-specific duration estimate.
- `compute_progress(...)`: derives `progress_pct` and `remaining_s` from slot states.
- `utcnow_iso()` / `parse_iso(...)`: timestamp normalization helpers.

Used only as a computation utility from `rest_api/app.py`.

## `rest_api/storage.py`

Run-directory mapping and path sanitization utilities.

- `RunStorageInfo`: canonical folder and filename tokens.
- `configure_runs_root(...)`: initializes active storage root and run index.
- `record_run_directory(...)`, `resolve_run_directory(...)`, `forget_run_directory(...)`: persistence and lookup.
- sanitizers for experiment names, optional subfolders, and timestamps.

This module is the single source of filesystem path normalization rules in REST code.

## `rest_api/nas.py`

SSH/rsync upload implementation:

- `NASConfig`: connection and retention settings.
- `NASManager`: setup, health probe, upload queue, retention cleanup.
- Upload logic is idempotent and marks successful runs with `UPLOAD_DONE`.

This path is retained for SSH-based deployments.

## `rest_api/nas_smb.py`

SMB/CIFS upload implementation:

- `SMBConfig`: SMB host/share credentials and mount options.
- `NASManager`: mount probe, upload queue, verification, retention loop.
- Upload worker mounts share, copies files, verifies count, then marks `UPLOAD_DONE`.

`rest_api/app.py` currently instantiates this manager for `/nas/*` endpoints.

## `rest_api/auto_flash_linux.py`

Host-side flash helper used by `/firmware/flash`:

- Finds matching CDC device by VID/PID.
- Sends boot command over serial.
- Invokes `dfu-util` to flash `.bin`.
- Waits for serial port to re-enumerate after flashing.

It is intentionally isolated from API route code so firmware flashing can evolve independently.
