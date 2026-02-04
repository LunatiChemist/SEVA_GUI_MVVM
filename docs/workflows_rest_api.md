# REST API Workflows

This document describes service-side workflows used by the GUI.

## Scope

- Device discovery and mode lookup
- Parameter validation endpoint
- Job lifecycle (start, status, cancel)
- Run artifact serving (files and zip)
- NAS/SMB setup, health, and upload
- Telemetry streaming endpoints

## Device Discovery and Capability Lookup

1. GUI calls `/devices` (adapter: `seva/adapters/device_rest.py`).
2. `rest_api/app.py` returns `DeviceInfo` list from in-memory registry.
3. GUI calls `/modes` and `/modes/{mode}/params` to build mode forms.

Operational note: `/admin/rescan` refreshes the registry from connected controllers.

## Validate Mode Parameters

1. GUI sends candidate payload to `/modes/{mode}/validate`.
2. `rest_api/app.py` delegates to `rest_api/validation.py`.
3. API returns `ValidationResult` with `errors` and `warnings`.

Acceptance behavior: GUI can block start when `ok=false` without touching hardware.

## Start Job and Run Slots

1. GUI submits `/jobs` with `JobRequest` (selected slots, modes, params, storage naming).
2. API validates slots and mode-param presence, reserves slots in `SLOT_RUNS`.
3. API computes `RunStorageInfo` via `rest_api/storage.py` and creates run directory.
4. API spawns per-slot worker threads to execute mode sequence.
5. Workers update `JobStatus` / `SlotStatus`; aggregate status is recomputed centrally.

Server status is authoritative: clients read `/jobs/{run_id}` or `/jobs` snapshots instead of deriving progress locally.

## Poll Status (Single and Bulk)

- `/jobs/{run_id}` returns latest snapshot with computed `progress_pct` and `remaining_s`.
- `/jobs/status/bulk` returns multiple snapshots in one request.
- `rest_api/progress_utils.py` computes progress based on timestamps and planned duration.

## Cancel Job

1. GUI sends `/jobs/{run_id}/cancel`.
2. API sets cancellation flag and updates queued slots immediately.
3. Worker loops observe the flag and transition running slots to terminal states.
4. API frees slot reservations once cancellation is complete.

## Browse and Download Artifacts

- `/runs/{run_id}/files`: list relative paths.
- `/runs/{run_id}/file?path=...`: serve one file with path traversal protection.
- `/runs/{run_id}/zip`: build in-memory ZIP and return as attachment.

`rest_api/storage.py` resolves run directories and enforces consistent mapping.

## NAS/SMB Setup, Health, and Upload

1. GUI posts `/nas/setup` with SMB settings.
2. `rest_api/nas_smb.py` stores config and probes connectivity.
3. API exposes `/nas/health` for status checks.
4. Upload is triggered automatically after successful runs or manually via `/runs/{run_id}/upload`.

Successful upload writes `UPLOAD_DONE`; retention jobs remove aged local directories.

## Telemetry Stream

- `/api/telemetry/temperature/latest`: latest sample cache snapshot.
- `/api/telemetry/temperature/stream`: SSE stream with periodic `temp` events and keepalive `ping` events.

This is currently mock data (`MockPotentiostatSource`) for UI streaming workflows.
