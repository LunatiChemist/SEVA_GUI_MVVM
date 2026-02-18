# REST API Classes and Modules

This document describes every Python module in `rest_api/` and how each one participates in the GUI -> API -> storage/device call-chain.

## Module inventory and integration map

The REST package currently contains the following Python modules:

- `rest_api/__init__.py`: package-level orientation docstring.
- `rest_api/app.py`: FastAPI entrypoint, route definitions, in-memory job/device registries, and worker orchestration.
- `rest_api/validation.py`: mode payload validators for `/modes/{mode}/validate`.
- `rest_api/progress_utils.py`: progress and ETA computations used in status snapshots.
- `rest_api/storage.py`: run-directory naming, sanitization, and persisted run-id path registry.
- `rest_api/nas_smb.py`: SMB/CIFS upload adapter used by `/nas/*` and `/runs/{run_id}/upload`.
- `rest_api/nas.py`: SSH/rsync NAS adapter kept for SSH-based deployments.
- `rest_api/auto_flash_linux.py`: Linux firmware flashing subprocess helper for `/firmware/flash`.
- `rest_api/update_package.py`: package-update contract validation, async worker, lock, and audit orchestration.
- `rest_api/mdns_service.py`: IPv4 mDNS registration helper for `_myapp._tcp.local.` service publication at startup/shutdown.

## `rest_api/app.py`

`app.py` is the only HTTP surface consumed by the GUI. It also manages process lifecycle hooks, including startup mDNS registration and shutdown deregistration via `rest_api/mdns_service.py`. The route families map to adapters and usecases as follows:

- Device discovery and mode metadata:
  - GUI callers: `seva/adapters/device_rest.py`
  - Endpoints: `/health`, `/devices`, `/devices/status`, `/modes`, `/modes/{mode}/params`
- Validation/start/poll/cancel/download:
  - GUI callers: `seva/adapters/job_rest.py`
  - Endpoints: `/modes/{mode}/validate`, `/jobs`, `/jobs/status`, `/jobs/{run_id}`, `/jobs/{run_id}/cancel`, `/runs/{run_id}/files`, `/runs/{run_id}/file`, `/runs/{run_id}/zip`
- Firmware flashing:
  - GUI callers: `seva/adapters/firmware_rest.py`
  - Endpoint: `/firmware/flash`
- Remote package updates:
  - GUI callers: `seva/adapters/update_rest.py`
  - Endpoints: `/updates/package`, `/updates/{update_id}`, `/updates`
- NAS management:
  - GUI callers: NAS settings flows through REST clients
  - Endpoints: `/nas/setup`, `/nas/health`, `/runs/{run_id}/upload`
- Telemetry demo stream:
  - Endpoint: `/api/telemetry/temperature/latest`, `/api/telemetry/temperature/stream`

### REST endpoint reference (`rest_api/app.py`)

The table below provides a practical, per-endpoint overview of method, purpose, and primary integration points.

| Method | Path | Handler | Purpose | Typical caller(s) |
|---|---|---|---|---|
| GET | `/version` | `version_info` | Returns API/runtime/build metadata for diagnostics and support. | Manual ops checks, service introspection |
| GET | `/health` | `health` | Basic service liveness + discovered device count. | `seva.adapters.discovery_http`, startup checks, mDNS post-discovery validation |
| GET | `/devices` | `list_devices` | Enumerates discovered potentiostat slots and port metadata. | `seva.adapters.device_rest` |
| GET | `/devices/status` | `list_device_status` | Returns slot state derived from active jobs (`idle/queued/running/...`). | GUI status polling |
| GET | `/modes` | `list_modes` | Lists available measurement modes exposed by controller integration. | GUI mode selectors |
| GET | `/modes/{mode}/params` | `mode_params` | Returns parameter schema/details for one measurement mode. | Dynamic parameter forms |
| POST | `/modes/{mode}/validate` | `validate_mode_params` | Validates mode payload via `validation.validate_mode_payload`. | Pre-flight form validation |
| POST | `/jobs/status` | `jobs_bulk_status` | Bulk status snapshots for many run IDs in one request. | `seva.adapters.job_rest` polling loops |
| GET | `/jobs` | `list_jobs` | Lists runs (supports filtering such as incomplete/completed and group). | Run overview panels |
| POST | `/jobs` | `start_job` | Creates a run, allocates slots, spawns worker threads, and initializes storage metadata. | Start-experiment use cases |
| POST | `/jobs/{run_id}/cancel` | `cancel_job` | Signals cancellation and updates queued/running slot states. | Cancel actions in GUI |
| GET | `/jobs/{run_id}` | `job_status` | Single-run detailed status snapshot with server-computed progress fields. | Per-run detail/polling |
| GET | `/runs/{run_id}/files` | `list_run_files` | Enumerates files in a run directory for browsing/download selection. | Result browser UI |
| GET | `/runs/{run_id}/file` | `get_run_file` | Streams a specific artifact file from run output. | Single-file downloads |
| GET | `/runs/{run_id}/zip` | `get_run_zip` | Streams zipped run artifacts for complete result export. | “Download all” actions |
| POST | `/nas/setup` | `nas_setup` | Persists SMB NAS configuration and performs initial connectivity probe. | NAS settings workflow |
| GET | `/nas/health` | `nas_health` | Reports current NAS connectivity state from manager probes. | NAS status indicator |
| POST | `/runs/{run_id}/upload` | `nas_upload_run` | Queues manual upload of one run to configured NAS target. | Post-run offload action |
| POST | `/admin/rescan` | `rescan` | Triggers fresh hardware discovery scan. | Admin/maintenance tools |
| POST | `/updates/package` | `start_package_update` | Stores update ZIP, acquires update lock, and enqueues async apply workflow. | `seva.adapters.update_rest` |
| GET | `/updates/{update_id}` | `get_package_update` | Returns server-authoritative package-update status, step, heartbeat, and error/audit details. | `seva.adapters.update_rest` |
| GET | `/updates` | `list_package_updates` | Lists recent package-update jobs for diagnostics. | Manual ops checks, update dashboards |
| POST | `/firmware/flash` | `flash_firmware` | Stores uploaded firmware binary and invokes Linux flashing subprocess flow. | `seva.adapters.firmware_rest` |
| GET | `/api/telemetry/temperature/latest` | `get_latest` | Returns latest cached telemetry sample per device (demo endpoint). | Telemetry demos |
| GET | `/api/telemetry/temperature/stream` | `temperature_stream` | SSE stream emitting periodic telemetry + keepalive pings (demo endpoint). | Streaming demo clients |

### Request/response behavior notes

- **Authentication boundary:** most operational endpoints check `x-api-key` via `require_key(...)`; keep adapter defaults aligned with deployment env vars (`BOX_API_KEY`).
- **Status authority:** `job_snapshot(...)` enriches `JobStatus` with `progress_pct` and `remaining_s` using `progress_utils.compute_progress(...)`; clients should treat these fields as authoritative.
- **Storage resolution:** run file/download/upload routes resolve directories through `storage.resolve_run_directory(...)` so callers should only persist `run_id`, never file-system paths.
- **Validation contract:** `/modes/{mode}/validate` always returns structured `ValidationResult` (`ok`, `errors`, `warnings`) to keep GUI feedback deterministic.

Important type contracts in `app.py`:

- `DeviceInfo`: discovered slot metadata (`slot`, `port`, optional serial number).
- `JobRequest`: request body for start-job orchestration (devices, modes, params, naming fields).
- `SlotStatus`: slot-local state machine (`idle|queued|running|done|failed|cancelled`) plus timestamps/files.
- `JobStatus`: run-level aggregate status with `progress_pct` and `remaining_s` from server computations.
- `JobOverview`: compact listing payload for `/jobs` list views.
- `JobStatusBulkRequest`: body schema for multi-run polling.
- `SMBSetupRequest`: NAS configuration payload.
- `TemperatureSample`, `LatestResponse`, `MockPotentiostatSource`: telemetry demo payload/model set.

Key orchestration functions:

- `_run_one_slot(...)` and `_run_slot_sequence(...)`: per-slot worker execution for single-mode or multi-mode runs.
- `_update_job_status_locked(...)`: recomputes aggregate job status from per-slot states.
- `job_snapshot(...)`: enriches snapshots with progress/remaining-time using `progress_utils`.
- `_build_run_storage_info(...)`: creates sanitized storage naming metadata from request fields.

## `rest_api/validation.py`

This module implements the validator dispatch used by `/modes/{mode}/validate`.

Core contracts:

- `ValidationIssue`: one machine-readable issue with `field`, `code`, and `message`.
- `ValidationResult`: response envelope with `ok`, `errors`, and `warnings`.
- `UnsupportedModeError`: thrown when no validator is registered for the requested mode.

Validation behavior summary:

- `CV` has explicit numeric and range checks plus quality warnings.
- `DC`, `AC`, `LSV`, `EIS`, `CDL`, `CA` currently verify required fields and return an explicit `not_implemented` warning.
- `validate_mode_payload(...)` normalizes mode tokens and dispatches to `_MODE_VALIDATORS`.

## `rest_api/progress_utils.py`

Pure computation module called from `app.py` status routes.

- `estimate_planned_duration(mode, params)`: computes expected duration for CV/CA/CP/OCP/LSV/PSTEP/GS/GCV/STEPSEQ/DC/EIS modes.
- `compute_progress(...)`: derives run-level `%` progress and remaining seconds from slot states and timestamps.
- `utcnow_iso()` and `parse_iso(...)`: UTC timestamp helpers used across job snapshots.

The output from this module is the server-authoritative progress signal consumed by GUI viewmodels.

## `rest_api/storage.py`

Single source of truth for run-path handling.

- `RunStorageInfo`: normalized folder and filename token bundle used during start-job.
- Sanitizers:
  - `sanitize_path_segment(...)`
  - `sanitize_optional_segment(...)`
  - `sanitize_client_datetime(...)`
- Registry persistence:
  - `record_run_directory(...)`
  - `resolve_run_directory(...)`
  - `forget_run_directory(...)`
  - `configure_runs_root(...)`

Persistence format:

- File: `<RUNS_ROOT>/_run_paths.json`
- Content: JSON object mapping `run_id` -> relative run path

## `rest_api/nas_smb.py`

Active NAS adapter for SMB/CIFS shares.

- `SMBConfig`: host/share credentials, mount options, retention configuration.
- `NASManager.setup(...)`: persists config + credentials and validates mountability.
- `NASManager.health(...)`: probes current connectivity.
- `NASManager.enqueue_upload(...)`: queues async upload workers.
- `NASManager._upload_worker(...)`: mounts share, copies run files via `rsync`, verifies file count, writes `UPLOAD_DONE` marker.
- Background tasks:
  - initial health probe
  - retention cleanup (deletes local runs after successful upload and retention window)

## `rest_api/nas.py`

SSH/rsync NAS adapter variant.

- `NASConfig`: SSH target and key configuration.
- `NASManager.setup(...)`: key provisioning + remote folder bootstrap.
- `NASManager.health(...)`: SSH key login probe.
- `NASManager.enqueue_upload(...)` / `_upload_worker(...)`: async rsync upload + minimal verification.
- Retention flow mirrors SMB manager behavior.

This module remains useful for environments where SMB mounts are unavailable.

## `rest_api/auto_flash_linux.py`

Subprocess utility invoked by `/firmware/flash`.

Execution chain:

1. receive `.bin` path as CLI arg
2. discover CDC serial port by VID/PID
3. send boot command (`BOOT_DFU_MODE`)
4. wait for DFU enumeration (`dfu-util -l`)
5. flash binary with `dfu-util`
6. wait for CDC serial to reappear

Failure behavior is exit-code driven so `app.py` can convert it into a typed HTTP error payload.

## `rest_api/update_package.py`

This module owns package-update orchestration used by `/updates/*`:

- manifest + checksum validation (`manifest.json`, `checksums.sha256`)
- ZIP path safety checks and SHA-256 verification
- service-wide single-job lock (`updates.locked`)
- asynchronous worker apply order (`pybeep` -> `rest_api` -> `firmware`)
- shared firmware flash callback reuse from `/firmware/flash` logic
- restart command execution and per-job restart result capture
- JSONL audit event writing per update id
