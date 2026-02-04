# SEVA Workflows

This document describes end-to-end GUI workflows and their call-chains.

## Start Experiment Batch

1. User triggers submit from `MainWindowView` toolbar (`seva/app/main.py`).
2. `RunFlowPresenter.start_run()` requests plan creation (`BuildExperimentPlan`).
3. Storage metadata is built (`BuildStorageMeta`).
4. `StartExperimentBatch` calls `JobPort.start_batch(...)` via `JobRestAdapter`.
5. `RunsRegistry` stores group metadata and presenter starts polling schedule.

Outcome: typed plan + storage metadata become backend jobs with tracked run-group state.

## Poll Group Status (authoritative)

1. `PollingScheduler` triggers periodic presenter poll callbacks.
2. Presenter calls `PollGroupStatus`.
3. `PollGroupStatus` fetches adapter payload through `JobPort.poll_group(...)`.
4. `normalize_status(...)` returns `GroupSnapshot` domain object.
5. `ProgressVM` converts snapshot to UI DTOs for `RunOverviewView` and `ChannelActivityView`.

Outcome: UI displays server-authoritative status/progress without local reconstruction.

## Download Group Results

1. User clicks download action in run overview/runs panel.
2. `DownloadController` resolves active group and storage metadata from presenter.
3. `DownloadGroupResults` downloads ZIPs (`JobPort.download_group_zip`), extracts files, normalizes slot folders.
4. Presenter records download path and refreshes runs panel status.

Outcome: artifacts land in deterministic folder structure tied to plan metadata.

## Cancel Workflow

- `RunFlowPresenter.cancel_active_group()` triggers `CancelGroup`.
- `RunFlowPresenter.cancel_selected_runs()` triggers `CancelRuns`.
- Use cases call `JobPort` cancel endpoints and translate adapter errors through `error_mapping`.

Outcome: cancellation behavior is centralized and error messages stay consistent.

## Discovery and Assignment Workflow

1. Settings dialog invokes discovery via `SettingsController` -> `DiscoveryController`.
2. `DiscoverAndAssignDevices` runs `DiscoverDevices` and merge/assignment logic.
3. Assigned URLs are written back into `SettingsVM` and persisted via `StorageLocal`.
4. App reapplies box configuration to plate/run/activity views.

Outcome: reachable boxes are discovered and mapped to box IDs without manual URL entry.

## Device, Relay, and Firmware Diagnostics

- `TestConnection` validates `/health` + `/devices` through `DeviceRestAdapter`.
- `PollDeviceStatus` maps slot statuses to `DeviceActivitySnapshot`.
- `TestRelay` and `SetElectrodeMode` use `RelayPort` abstractions.
- `FlashFirmware` validates firmware path and flashes each selected box.

Outcome: diagnostics and control actions remain use-case driven and adapter-agnostic.

## Layout Save/Load Workflow

1. User saves layout from toolbar; `SavePlateLayout` serializes selected wells and params.
2. `StorageLocal` persists JSON payload atomically.
3. User loads layout; `LoadPlateLayout` restores selection and parameters into view models.
4. Views update through existing VM-driven callbacks.

Outcome: plate configuration can be persisted and restored without embedding storage logic in views.
