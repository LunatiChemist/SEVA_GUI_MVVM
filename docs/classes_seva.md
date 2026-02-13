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

Domain invariants enforced in constructors:

- all identity wrappers (`GroupId`, `RunId`, `WellId`, `BoxId`, `ModeName`) reject blank strings
- timestamp wrappers (`ClientDateTime`, `ServerDateTime`) require timezone-aware `datetime`
- scalar wrappers (`ProgressPct`, `Seconds`) normalize numeric input and reject out-of-range values
- `ExperimentPlan` requires at least one `WellPlan`; `GroupSnapshot` validates typed map keys/values

Typical call chain:

- `ExperimentViewModel` field snapshots -> `build_experiment_plan.py` -> `PlanMeta`/`WellPlan`/`ExperimentPlan`
- `JobPort.poll_group` adapter payload -> `poll_group_status.py` -> `snapshot_normalizer.py` -> `GroupSnapshot`

### Mode registry and parameters

- `seva/domain/modes.py`: `ModeRegistry` and `ModeRule` own normalization, labels, and mode-specific form filtering.
- `seva/domain/params/*.py`: typed mode parameter builders (`CVParams`, `ACParams`, `DCParams`, `EISParams`, `CDLParams`) and payload serialization.

Mode registry responsibilities (single source of truth):

- normalize mode keys for lookups (`_normalize_key`) and backend token mapping (`backend_token`)
- provide UI labels (`label_for`) and clipboard targets (`clipboard_attr_for`)
- determine mode-owned fields (`is_mode_field`, `filter_fields`) so ViewModels avoid hardcoded field lists
- map mode names to typed parameter builders (`builder_for`) used by plan construction use cases

Parameter schema mapping examples:

- `CVParams.from_form` reads `cv.*` keys and serializes to compact CV payload fields (`start`, `vertex1`, ...)
- `ACParams.from_form` reads `ea.*` + `control_mode`, derives `voltage_v`/`current_ma`, and omits empty values
- each params class extracts run flags (`run_*`, `eval_cdl`) into `ModeParams.flags` for mode toggles

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
- `seva/domain/ports.py`: hexagonal ports (`JobPort`, `DevicePort`, `StoragePort`, `RelayPort`, `FirmwarePort`, `UpdatePort`).
- `seva/domain/device_activity.py`: typed activity snapshot objects for channel activity UI.

### Reserved compatibility modules

- `seva/domain/models.py`: compatibility placeholder pointing to `entities`.
- `seva/domain/errors.py` and `seva/domain/validation.py`: reserved extension points for shared domain-wide rules.

## Adapters (`seva/adapters`)

### Shared transport and error handling

- `http_client.py`: `RetryingSession` and `HttpConfig` centralize API-key headers, timeout policy, retry loops, and multipart reset behavior before upload retries.
- `api_errors.py`: typed adapter error hierarchy (`ApiClientError`, `ApiServerError`, `ApiTimeoutError`) plus payload parsing helpers consumed by use-case error mapping (`seva/usecases/error_mapping.py`).

### REST adapters implementing ports

- `job_rest.py` (`JobPort`): implements run lifecycle transport and payload mapping.
  - consumed by `StartExperimentBatch`, `PollGroupStatus`, `CancelGroup`, `CancelRuns`, and `DownloadGroupResults` (wired in `seva/app/controller.py`)
  - translates `ExperimentPlan` wells into `POST /jobs` payloads (`devices`, `modes`, `params_by_mode`, metadata)
  - polls `POST /jobs/status` and returns server-authoritative snapshot dictionaries for domain normalization
  - downloads `GET /runs/{run_id}/zip` artifacts and writes grouped ZIP files under `<target>/<group>/<box>/`
  - raises typed adapter errors from `seva/adapters/api_errors.py`
- `device_rest.py` (`DevicePort`): implements metadata and capability reads.
  - consumed by `TestConnection` and `PollDeviceStatus`
  - calls `/health`, `/devices`, `/devices/status`, `/modes`, `/modes/{mode}/params`
  - normalizes mode keys and caches mode lists/schemas per box
  - raises typed adapter errors from `seva/adapters/api_errors.py`
- `firmware_rest.py` (`FirmwarePort`): implements direct/staged flashing operations (`/firmware/flash`, `/firmware/flash/staged`).
  - consumed by `FlashStagedFirmware` (settings flow)
  - performs multipart upload or JSON post with shared retry/timeout policy
  - raises typed adapter errors from `seva/adapters/api_errors.py`
- `update_rest.py` (`UpdatePort`): implements remote update and version transport.
  - consumed by `UploadRemoteUpdate`, `PollRemoteUpdateStatus`, `FetchBoxVersionInfo`
  - calls `/updates`, `/updates/{id}`, and `/version`
  - normalizes responses into domain update types (`UpdateStartResult`, `UpdateStatus`, `BoxVersionInfo`)
  - raises typed adapter errors from `seva/adapters/api_errors.py`
- `discovery_http.py` (`DeviceDiscoveryPort`): implements host/base-url/CIDR discovery.
  - consumed by `DiscoverDevices` and `DiscoverAndAssignDevices`
  - expands CIDR ranges, probes `/version` for identity and `/health` for enrichment
  - deduplicates discovered `base_url` values before returning domain `DiscoveredBox` objects

### Local/test adapters

- `storage_local.py` (`StoragePort`): JSON persistence for layouts and user settings.
  - consumed by `SavePlateLayout`, `LoadPlateLayout`, `RunFlowCoordinator` registry/settings interactions, and app/settings/discovery controllers
  - enforces `layout_*.json` naming and uses atomic write (`tempfile` + `os.replace`) for `user_settings.json`
- `job_rest_mock.py`: in-memory `JobPort` implementation for offline tests and deterministic run-state simulation.
- `relay_mock.py`: stub `RelayPort` implementation consumed by `TestRelay` and `SetElectrodeMode` in non-hardware environments.

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
- `upload_remote_update.py`: one-box remote update upload orchestration.
- `poll_remote_update_status.py`: one-box update polling orchestration.
- `fetch_box_version_info.py`: one-box `/version` lookup orchestration.
- `flash_staged_firmware.py`: multi-box staged firmware flashing.

### Layout and persistence workflows

- `save_plate_layout.py` / `load_plate_layout.py`: plate snapshot persistence and restore.
- `apply_ir_correction.py`: reserved placeholder for future post-processing.
- `error_mapping.py`: central adapter-to-usecase error translation.

## ViewModels (`seva/viewmodels`)

- `experiment_vm.py` (`ExperimentVM`)
  - bound view: `seva/app/views/experiment_panel_view.py`
  - app wiring: `App._on_apply_params`, `App._on_copy_mode`, `App._on_paste_mode`, `App._on_selection_changed`
  - usecase dependency (read-only): `RunFlowPresenter._build_plan_request` consumes `well_params` snapshots
  - state owned: flat live form (`fields`), grouped per-well snapshots (`well_params`), mode clipboards
- `plate_vm.py` (`PlateVM`)
  - bound view: `seva/app/views/well_grid_view.py`
  - app wiring: selection callback to `App._on_selection_changed`; command intents to app methods
  - usecase dependency (indirect): `RunFlowPresenter` reads `configured()` and `get_selection()` for start/cancel payloads
  - state owned: selected wells, configured wells, box-prefix helpers
- `progress_vm.py` (`ProgressVM`)
  - bound views: `seva/app/views/run_overview_view.py`, `seva/app/views/channel_activity_view.py`
  - app wiring: callbacks `App._apply_run_overview` and `App._apply_channel_activity`
  - usecase dependency: consumes `GroupSnapshot` from `PollGroupStatus`; consumes `DeviceActivitySnapshot` from `PollDeviceStatus`
  - state owned: active group id, last snapshot cache, derived well/box/activity DTOs
- `runs_vm.py` (`RunsVM`)
  - bound view: `seva/app/views/runs_panel_view.py`
  - app wiring: `RunFlowPresenter._refresh_runs_panel` and selection sync
  - usecase dependency: projects `RunsRegistry` entries that are fed by `RunFlowCoordinator` events
  - state owned: currently active group id for runs panel
- `settings_vm.py` (`SettingsVM`, `SettingsConfig`)
  - bound view/controller: `seva/app/settings_controller.py` + `SettingsDialog`
  - app wiring: loaded at startup in `App._load_user_settings`; consumed by `AppController.ensure_ready`
  - usecase dependency: parameters passed into `BuildStorageMeta`, `StartExperimentBatch`, polling cadence, diagnostics, discovery, remote update upload/poll/version refresh
  - state owned: typed runtime config, API URLs/keys, remote update ZIP path, dialog-only fields (`experiment_name`, `subdir`, relay/debug flags)
- `live_data_vm.py` (`LiveDataVM`)
  - bound view: standalone plotter (`seva/app/dataplotter_standalone.py`)
  - usecase dependency: none currently; reserved for future post-processing workflows
  - state owned: include toggles per well, axes, section filter, IR correction text
- `status_format.py`
  - pure helper module used by `ProgressVM` and `RunsVM`
  - responsibility: normalize/label run phases so views never hardcode status-text mapping

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
