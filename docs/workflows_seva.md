# SEVA Workflows

This document describes end-to-end GUI workflows and their call-chains.

## UI Entrypoints and Handoffs

The desktop app boots in `seva/app/main.py` (`main()` -> `App()`), then wires
views, viewmodels, and controller/presenter objects.

- Toolbar `Start` (`MainWindowView.on_submit`) -> `App._on_submit()` ->
  `RunFlowPresenter.start_run()` -> `BuildExperimentPlan` + `BuildStorageMeta` ->
  `RunFlowCoordinator.start()` -> `StartExperimentBatch`.
- Toolbar `Cancel Group` (`MainWindowView.on_cancel_group`) ->
  `App._on_cancel_group()` -> `RunFlowPresenter.cancel_active_group()` ->
  `CancelGroup`.
- Toolbar `Save Layout` / `Load Layout` -> `App._on_save_layout()` /
  `App._on_load_layout()` -> `SavePlateLayout` / `LoadPlateLayout` via
  `StorageLocal`.
- Experiment panel field edits (`ExperimentPanelView.on_change`) ->
  `ExperimentVM.set_field(...)`; `Update Parameters` ->
  `App._on_apply_params()` updates `ExperimentVM` and `PlateVM`.
- Experiment panel `End Selection` -> `App._on_end_selection()` ->
  `RunFlowPresenter.cancel_selected_runs()` -> `CancelRuns` (if available).
- Run overview `Download Group` / per-box download ->
  `DownloadController.download_group_results()` -> `DownloadGroupResults`.
- Runs tab row actions (`select/open/cancel/delete`) ->
  `RunFlowPresenter.on_runs_*` methods.
- Settings `Save` / `Test` / `Scan Network` / firmware actions ->
  `SettingsController` and `DiscoveryController`, which call usecases and write
  results back into `SettingsVM`.

These paths keep views UI-only: widgets emit callbacks, viewmodels hold UI
state, and usecases/adapters execute network/storage operations.

## Start Experiment Batch

1. User triggers submit from `MainWindowView` toolbar (`seva/app/main.py`).
2. `RunFlowPresenter.start_run()` requests plan creation (`BuildExperimentPlan`).
3. Storage metadata is built (`BuildStorageMeta`).
4. `StartExperimentBatch` calls `JobPort.start_batch(...)` via `JobRestAdapter`.
5. `JobRestAdapter.start_batch(...)` maps each `WellPlan` into one `POST /jobs` request per box slot with:
   - `devices` from slot registry (`slot01`, `slot02`, ...)
   - normalized `modes`
   - `params_by_mode` from typed `ModeParams.to_payload()`
   - shared plan metadata (`group_id`, timestamps, experiment name, output settings)
5. `RunsRegistry` stores group metadata and presenter starts polling schedule.

Outcome: typed plan + storage metadata become backend jobs with tracked run-group state.

## Poll Group Status (authoritative)

1. `PollingScheduler` triggers periodic presenter poll callbacks.
2. Presenter calls `PollGroupStatus`.
3. `PollGroupStatus` fetches adapter payload through `JobPort.poll_group(...)`.
4. `JobRestAdapter.poll_group(...)` posts pending IDs to `/jobs/status`, merges with cached terminal runs, and emits snapshot dictionaries.
5. `normalize_status(...)` returns `GroupSnapshot` domain object.
5. `ProgressVM` converts snapshot to UI DTOs for `RunOverviewView` and `ChannelActivityView`.

Outcome: UI displays server-authoritative status/progress without local reconstruction.

## Download Group Results

1. User clicks download action in run overview/runs panel.
2. `DownloadController` resolves active group and storage metadata from presenter.
3. `DownloadGroupResults` downloads ZIPs (`JobPort.download_group_zip`), extracts files, normalizes slot folders.
4. `JobRestAdapter.download_group_zip(...)` streams `GET /runs/{run_id}/zip` responses to disk under `<results_root>/<group>/<box>/`.
4. Presenter records download path and refreshes runs panel status.

Outcome: artifacts land in deterministic folder structure tied to plan metadata.

## Cancel Workflow

- `RunFlowPresenter.cancel_active_group()` triggers `CancelGroup`.
- `RunFlowPresenter.cancel_selected_runs()` triggers `CancelRuns`.
- Use cases call `JobPort` cancel endpoints; `JobRestAdapter` issues `POST /jobs/{run_id}/cancel`.
- Use cases translate adapter errors through `error_mapping`.

Outcome: cancellation behavior is centralized and error messages stay consistent.

## Discovery and Assignment Workflow

1. Settings dialog invokes discovery via `SettingsController` -> `DiscoveryController`.
2. `DiscoverAndAssignDevices` runs `DiscoverDevices` and merge/assignment logic.
3. `HttpDiscoveryAdapter.discover(...)` expands host/CIDR candidates, probes `/version`, then enriches with `/health`.
3. Assigned URLs are written back into `SettingsVM` and persisted via `StorageLocal`.
4. App reapplies box configuration to plate/run/activity views.

Outcome: reachable boxes are discovered and mapped to box IDs without manual URL entry.

## Device, Relay, and Firmware Diagnostics

- `TestConnection` validates `/health` + `/devices` through `DeviceRestAdapter`.
- `PollDeviceStatus` maps slot statuses to `DeviceActivitySnapshot` using `DeviceRestAdapter` (`/devices/status` and `/devices`).
- `TestRelay` and `SetElectrodeMode` use `RelayPort` abstractions.
- `FlashFirmware` validates firmware path and flashes each selected box through `FirmwareRestAdapter` (`POST /firmware/flash` multipart upload).

Outcome: diagnostics and control actions remain use-case driven and adapter-agnostic.

## Layout Save/Load Workflow

1. User saves layout from toolbar; `SavePlateLayout` serializes selected wells and params.
2. `StorageLocal` persists JSON payload atomically.
3. User loads layout; `LoadPlateLayout` restores selection and parameters into view models.
4. Views update through existing VM-driven callbacks.

Outcome: plate configuration can be persisted and restored without embedding storage logic in views.

## Adapter-to-UseCase Port Mapping Reference

- `JobPort` (`JobRestAdapter`, `JobRestMock`)
  - use cases: `StartExperimentBatch`, `PollGroupStatus`, `CancelGroup`, `CancelRuns`, `DownloadGroupResults`
- `DevicePort` (`DeviceRestAdapter`)
  - use cases: `TestConnection`, `PollDeviceStatus`
- `FirmwarePort` (`FirmwareRestAdapter`)
  - use case: `FlashFirmware`
- `StoragePort` (`StorageLocal`)
  - use cases: `SavePlateLayout`, `LoadPlateLayout`, `RunFlowCoordinator` persistence flows
- `RelayPort` (`RelayMock` in app composition)
  - use cases: `TestRelay`, `SetElectrodeMode`
- `DeviceDiscoveryPort` (`HttpDiscoveryAdapter`)
  - use cases: `DiscoverDevices`, `DiscoverAndAssignDevices`
