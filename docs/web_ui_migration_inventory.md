# Web UI Migration Inventory (Tkinter to React)

This document maps the existing Tkinter UI responsibilities to the new Web UI track and records the Web command/query contracts needed for feature parity.

The mapping follows repository boundaries:

- Views: rendering and user input only.
- ViewModels: UI state and commands only.
- Services/UseCases: workflow orchestration and validation flow.
- Adapters: HTTP transport, localStorage, and browser file APIs.

## Scope and assumptions

- Two-track runtime remains active: Tkinter desktop UI and Web UI both exist.
- Web UI is desktop-browser focused.
- Backend REST behavior is unchanged; server status remains authoritative.
- API key stays optional and only applies when backend enforces it.

## Tkinter to Web feature map

| Tkinter area/action | Current module(s) | Web view | Web viewmodel/service command | REST/API contract |
| --- | --- | --- | --- | --- |
| Start run | `seva/app/main.py`, `seva/app/run_flow_presenter.py` | `views/RunPlannerView.tsx` | `RunWorkflowViewModel.startGroup(command)` | `POST /jobs` per run entry |
| Cancel active group | `run_flow_presenter.cancel_active_group` | `views/RunMonitorView.tsx` | `RunWorkflowViewModel.cancelGroup(groupId)` | `POST /jobs/{run_id}/cancel` for tracked run ids |
| End selection / cancel subset | `run_flow_presenter.cancel_selected_runs` | `views/RunMonitorView.tsx` | `RunWorkflowViewModel.cancelRuns(runRefs)` | `POST /jobs/{run_id}/cancel` |
| Poll progress/status | `run_flow_presenter._on_poll_tick` | `views/RunMonitorView.tsx` | `RunWorkflowViewModel.pollGroup(groupId)` | `POST /jobs/status` |
| Download group results | `seva/app/download_controller.py` | `views/RunMonitorView.tsx` | `RunWorkflowViewModel.downloadGroup(groupId)` | `GET /runs/{run_id}/zip` |
| Run list/history | `seva/viewmodels/runs_vm.py` | `views/RunHistoryView.tsx` | `RunHistoryViewModel` backed by run store | client state + optional `GET /jobs` refresh |
| Settings edit/save | `seva/app/views/settings_dialog.py`, `seva/viewmodels/settings_vm.py` | `views/SettingsView.tsx` | `SettingsViewModel.save(settings)` | localStorage adapter, no immediate backend write |
| Settings connection test | `settings_controller.handle_test_connection` | `views/SettingsView.tsx` | `SettingsViewModel.testConnection(boxId)` | `GET /health`, `GET /devices` |
| Device discovery | `seva/app/discovery_controller.py` | `views/DiscoveryView.tsx` | `DiscoveryViewModel.scan(candidates)` | `GET /health`, `GET /version`, `GET /devices`, optional `POST /admin/rescan` |
| Firmware flash | `settings_controller.handle_flash_firmware` | `views/FirmwareView.tsx` | `FirmwareViewModel.flashAll(file)` | `POST /firmware/flash` |
| NAS setup/health/upload | `seva/app/nas_gui_smb.py` | `views/NasView.tsx` | `NasViewModel.setup/health/upload` | `POST /nas/setup`, `GET /nas/health`, `POST /runs/{run_id}/upload` |
| Mode metadata + validate | `device_rest.get_modes/get_mode_schema`, `/modes/{mode}/validate` | `views/RunPlannerView.tsx` | `RunWorkflowViewModel.loadModeMetadata/validateMode` | `GET /modes`, `GET /modes/{mode}/params`, `POST /modes/{mode}/validate` |
| Channel activity | `ProgressVM.apply_device_activity` | `views/DeviceStatusView.tsx` | `DeviceStatusViewModel.refresh()` | `GET /devices/status` |
| Data plotting entrypoint | `seva/app/dataplotter_standalone.py` | `views/DataPlotterView.tsx` | `TelemetryViewModel` (poll/SSE) | `GET /api/telemetry/temperature/latest`, `GET /api/telemetry/temperature/stream` |

## Web command and DTO contracts

### Settings DTOs

- `BoxConnectionDto`
  - `boxId: string`
  - `baseUrl: string`
  - `apiKey: string`
- `WebSettingsDto`
  - `version: 1`
  - `boxes: BoxConnectionDto[]`
  - `requestTimeoutS: number`
  - `downloadTimeoutS: number`
  - `pollIntervalMs: number`
  - `pollBackoffMaxMs: number`
  - `resultsDir: string`
  - `experimentName: string`
  - `subdir: string`
  - `autoDownloadOnComplete: boolean`
  - `useStreaming: boolean`
  - `debugLogging: boolean`
  - `relayIp: string`
  - `relayPort: number`
  - `firmwarePathHint: string`

### Run DTOs

- `RunEntryDto`
  - `wellId: string`
  - `boxId: string`
  - `slot: string` (for example `slot01`)
  - `modes: string[]`
  - `paramsByMode: Record<string, Record<string, unknown>>`
- `StartGroupCommand`
  - `groupId: string`
  - `clientDateTime: string` (ISO-8601 UTC)
  - `experimentName: string`
  - `subdir?: string`
  - `entries: RunEntryDto[]`
- `RunRefDto`
  - `groupId: string`
  - `boxId: string`
  - `runId: string`

### Discovery and diagnostics DTOs

- `DiscoveryCandidateDto`
  - `baseUrl: string`
  - `apiKey?: string`
- `DiscoveryResultDto`
  - `baseUrl: string`
  - `ok: boolean`
  - `health?: object`
  - `version?: object`
  - `devices?: object`
  - `error?: string`

## Adapter boundary rules for web implementation

- HTTP adapter normalizes all endpoint payloads to typed DTOs before returning.
- ViewModels and services only consume typed DTOs, never raw fetch JSON.
- Typed adapter errors include `status`, `code`, `message`, and optional `hint`.
- View layer shows technical errors and does not swallow exceptions.

## Legacy and deletion guidance

- No legacy fallback branch is introduced inside Web code paths.
- Tkinter remains intentionally supported as the second runtime track.
- When Web path replaces temporary scaffolding in later milestones, scaffold code must be deleted instead of kept as fallback.

