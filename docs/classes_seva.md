# SEVA Classes and Modules

This document maps the GUI code in `seva/` to MVVM + Hexagonal layers.

## Scope

- Domain models and registries (`seva/domain`)
- Ports and adapter implementations (`seva/domain/ports.py`, `seva/adapters`)
- Use-case orchestration (`seva/usecases`)
- ViewModels and UI composition (`seva/viewmodels`, `seva/app`)

## Layer Boundaries

- Views: render and event wiring only.
- ViewModels: UI state + commands only.
- UseCases: orchestration and workflow sequencing.
- Adapters: external I/O implementations.
- Domain: typed objects, validation, naming, and normalization helpers.

## Domain (`seva/domain`)

### Core entities

`seva/domain/entities.py` defines immutable value objects and aggregates used above adapter boundaries:

- identity/value objects: `GroupId`, `RunId`, `WellId`, `BoxId`, `ModeName`
- time and scalar wrappers: `ClientDateTime`, `ServerDateTime`, `ProgressPct`, `Seconds`
- planning aggregates: `ModeParams`, `PlanMeta`, `WellPlan`, `ExperimentPlan`
- polling aggregates: `RunStatus`, `BoxSnapshot`, `GroupSnapshot`

### Mode registry and parameters

- `seva/domain/modes.py`: `ModeRegistry` and `ModeRule` own normalization, labels, and mode-specific form filtering.
- `seva/domain/params/*.py`: typed mode parameter builders (`CVParams`, `ACParams`, `DCParams`, `EISParams`, `CDLParams`) and payload serialization.

### Mapping and normalization helpers

- `seva/domain/mapping.py`: box/slot to well-id mapping and slot parsing.
- `seva/domain/naming.py`: deterministic group-id generation.
- `seva/domain/time_utils.py`: timezone-aware parsing of client timestamps.
- `seva/domain/snapshot_normalizer.py`: adapter payload to `GroupSnapshot` normalization.
- `seva/domain/layout_utils.py`: selection normalization for layout operations.
- `seva/domain/storage_meta.py`: `StorageMeta` for output path metadata.

### Domain registries and contracts

- `seva/domain/runs_registry.py`: persistent registry for run groups and runtime attachment points.
- `seva/domain/discovery.py`: discovery contracts (`DiscoveredBox`, `DeviceDiscoveryPort`).
- `seva/domain/ports.py`: hexagonal ports (`JobPort`, `DevicePort`, `StoragePort`, `RelayPort`, `FirmwarePort`).
- `seva/domain/device_activity.py`: typed activity snapshot objects for channel activity UI.

### Reserved compatibility modules

- `seva/domain/models.py`: compatibility placeholder pointing to `entities`.
- `seva/domain/errors.py` and `seva/domain/validation.py`: reserved extension points for shared domain-wide rules.

## Adapters (`seva/adapters`)

### Shared transport and error handling

- `http_client.py`: `RetryingSession` and `HttpConfig` centralize API key headers, retries, and timeouts.
- `api_errors.py`: typed adapter error hierarchy (`ApiClientError`, `ApiServerError`, `ApiTimeoutError`) plus payload parsing helpers.

### REST adapters implementing ports

- `job_rest.py` (`JobPort`): start, poll, cancel, and download workflows; server status is authoritative.
- `device_rest.py` (`DevicePort`): health/device list/mode metadata access.
- `firmware_rest.py` (`FirmwarePort`): firmware upload and flash endpoint.
- `discovery_http.py` (`DeviceDiscoveryPort`): parallel `/version` + `/health` probing for host/CIDR candidates.

### Local/test adapters

- `storage_local.py` (`StoragePort`): JSON persistence for layouts and user settings.
- `job_rest_mock.py`: in-memory `JobPort` implementation for offline tests.
- `relay_mock.py`: stub `RelayPort` implementation for non-hardware environments.

## UseCases (`seva/usecases`)

### Plan and metadata construction

- `build_experiment_plan.py`: builds typed `ExperimentPlan` from UI snapshots.
- `build_storage_meta.py`: derives `StorageMeta` used for artifact output paths.

### Runtime orchestration

- `start_experiment_batch.py`: submits plan via `JobPort`.
- `poll_group_status.py`: returns normalized, server-authoritative `GroupSnapshot`.
- `download_group_results.py`: downloads and unpacks run artifacts.
- `cancel_group.py` / `cancel_runs.py`: run cancellation orchestration.
- `run_flow_coordinator.py`: stateful start/poll/download coordination with hooks.

### Discovery and diagnostics

- `discover_devices.py`: candidate probing and registry merge helpers.
- `discover_and_assign_devices.py`: combined discovery + assignment operation.
- `poll_device_status.py`: per-channel status snapshots for activity UI.
- `test_connection.py`: health + device diagnostics for a box.
- `test_relay.py`, `set_electrode_mode.py`: relay diagnostics/configuration.
- `flash_firmware.py`: multi-box firmware flashing.

### Layout and persistence workflows

- `save_plate_layout.py` / `load_plate_layout.py`: plate snapshot persistence and restore.
- `apply_ir_correction.py`: reserved placeholder for future post-processing.
- `error_mapping.py`: central adapter-to-usecase error translation.

## ViewModels (`seva/viewmodels`)

- `experiment_vm.py`: form field state, per-well parameter snapshots, mode-aware copy/paste.
- `plate_vm.py`: selected/configured well state and plate-level UI commands.
- `progress_vm.py`: transforms snapshots into run-overview and channel-activity DTOs.
- `runs_vm.py`: converts registry entries into runs-panel rows.
- `settings_vm.py`: typed runtime config plus settings command callbacks.
- `live_data_vm.py`: live data plot include/axis/section state.
- `status_format.py`: status normalization and display-label helpers.

## App and Views (`seva/app`, `seva/app/views`)

### App composition and controllers

- `main.py`: application bootstrap and top-level event wiring.
- `controller.py`: adapter/use-case construction based on settings.
- `run_flow_presenter.py`: UI-facing orchestration glue for start/cancel/poll/download.
- `settings_controller.py`, `download_controller.py`, `discovery_controller.py`: dialog/action specific controllers.
- `polling_scheduler.py`: scheduler abstraction for group polling timers.
- `nas_gui_smb.py`: standalone NAS setup helper UI.

### View modules

- `views/main_window.py`: top-level window and toolbar/tab layout.
- `views/well_grid_view.py`: plate grid widget and selection interactions.
- `views/experiment_panel_view.py`: mode parameter editor panel.
- `views/run_overview_view.py`: per-box and per-well progress display.
- `views/channel_activity_view.py`: channel activity visualization.
- `views/runs_panel_view.py`: run-group table with actions.
- `views/settings_dialog.py`: settings modal UI.
- `views/discovery_results_dialog.py`: discovery result display dialog.
