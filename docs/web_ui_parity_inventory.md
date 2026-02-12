# Web UI Parity Inventory

This inventory maps the current Tkinter UI actions to NiceGUI pages/components and command handlers.

## Scope

The migration runs Tkinter and NiceGUI in parallel. Tkinter remains available while this inventory is closed out.

## Main Window + Toolbar

- `Start` (`seva/app/views/main_window.py`):
  NiceGUI component: top action bar `Start` button.
  Handler: `WebRuntime.start_run()`.
  Status: Implemented.

- `Cancel Group` (`seva/app/views/main_window.py`):
  NiceGUI component: top action bar `Cancel Group` button.
  Handler: `WebRuntime.cancel_active_group()`.
  Status: Implemented.

- `Save Layout` (`seva/app/views/main_window.py`):
  NiceGUI component: Layout actions in `Plate` tab.
  Handler: `SavePlateLayout` use case via `WebRuntime.save_layout_payload()`.
  Status: Implemented.

- `Load Layout` (`seva/app/views/main_window.py`):
  NiceGUI component: Layout actions in `Plate` tab.
  Handler: `LoadPlateLayout` use case via `WebRuntime.load_layout_payload()`.
  Status: Implemented.

- `Settings` (`seva/app/views/main_window.py`):
  NiceGUI component: dedicated `Settings` tab.
  Handler: settings save/test/discovery methods on `WebRuntime`.
  Status: Implemented.

- `Data Plotter` (`seva/app/views/main_window.py`):
  NiceGUI component: dedicated `Data Plotter` tab.
  Handler: browser CSV upload/plot interactions in `seva/web_ui/plotter_vm.py`.
  Status: Implemented (migrated in final stage).

## Well Grid (`WellGridView`)

- Select one/multiple wells:
  NiceGUI component: selectable 4-box well button matrix.
  Handler: `PlateVM.set_selection(...)` through thin web binding VM.
  Status: Implemented.

- Context copy/paste semantics:
  NiceGUI component: mode-level copy/paste controls in `Experiment` tab.
  Handler: `ExperimentVM.cmd_copy_mode(...)` and `ExperimentVM.cmd_paste_mode(...)`.
  Status: Implemented.

- Reset selected/all well config:
  NiceGUI component: `Reset Selected` and `Reset All` buttons.
  Handler: `WebRuntime.reset_selected_wells()` and `WebRuntime.reset_all_wells()`.
  Status: Implemented.

## Experiment Panel (`ExperimentPanelView`)

- CV/DCAC/CDL/EIS field editing:
  NiceGUI component: grouped cards with matching field IDs.
  Handler: `ExperimentVM.set_field(field_id, value)`.
  Status: Implemented.

- `Update Parameters`:
  NiceGUI component: `Apply Parameters` button.
  Handler: `WebRuntime.apply_params_to_selection()`.
  Status: Implemented.

- `End Selection`:
  NiceGUI component: `End Selection` button.
  Handler: `WebRuntime.cancel_selected_runs()`.
  Status: Implemented.

- `End Task`:
  NiceGUI component: `End Task` button.
  Handler: `WebRuntime.cancel_active_group()`.
  Status: Implemented.

- Electrode mode toggle (`2E`/`3E`):
  NiceGUI component: segmented control.
  Handler: `ExperimentVM.set_electrode_mode(...)` + `SetElectrodeMode` use case.
  Status: Implemented.

## Run Overview (`RunOverviewView`)

- Per-box status/progress cards:
  NiceGUI component: responsive summary cards.
  Handler: `ProgressVM` DTO projections rendered in web view.
  Status: Implemented.

- Per-well table:
  NiceGUI component: table bound to `ProgressVM` DTO rows.
  Handler: `ProgressVM.apply_snapshot(...)` updates web state.
  Status: Implemented.

- `Download Group` and box-scoped download action:
  NiceGUI component: run-overview action buttons.
  Handler: `DownloadGroupResults` use case via `WebRuntime.download_group_results()`.
  Status: Implemented.

## Channel Activity (`ChannelActivityView`)

- Activity matrix by well + updated-at label:
  NiceGUI component: color-coded grid with timestamp.
  Handler: `PollDeviceStatus` use case -> `ProgressVM.apply_device_activity(...)`.
  Status: Implemented.

## Runs Panel (`RunsPanelView`)

- List historical run groups:
  NiceGUI component: runs table.
  Handler: `RunsVM.rows()`.
  Status: Implemented.

- Select run group:
  NiceGUI component: table row select.
  Handler: `WebRuntime.select_group(...)` and `ProgressVM.set_active_group(...)`.
  Status: Implemented.

- Cancel/remove run group:
  NiceGUI component: runs actions.
  Handler: `CancelGroup` use case and `RunsRegistry.remove(...)`.
  Status: Implemented.

## Settings (`SettingsDialog`)

- Four box URLs + API keys:
  NiceGUI component: settings form rows A/B/C/D.
  Handler: `SettingsVM.apply_dict(...)` through web settings binding VM.
  Status: Implemented.

- Test connection per box:
  NiceGUI component: `Test` button per box row.
  Handler: `AppController.build_test_connection(...)`.
  Status: Implemented.

- Device discovery:
  NiceGUI component: `Scan Network` button.
  Handler: `DiscoverAndAssignDevices` use case.
  Status: Implemented.

- Poll/request/download timeout and results dir settings:
  NiceGUI component: numeric/text inputs.
  Handler: `SettingsVM.apply_dict(...)`.
  Status: Implemented.

- Browser persistence + JSON import/export:
  NiceGUI component: save/import/export controls in settings tab.
  Handler: browser `localStorage` bridge + compatibility loader into `SettingsVM.apply_dict(...)`.
  Status: Implemented.

## Deferred (Migrate-Last Group)

- Firmware flashing:
  NiceGUI component: `Firmware` tab.
  Handler: `FlashFirmware` use case.
  Status: Implemented (migrated in final stage).

- NAS setup/health/upload:
  NiceGUI component: `NAS` tab.
  Handler: dedicated NAS HTTP adapter + use-case orchestration.
  Status: Implemented (migrated in final stage).

- Data plotter workflow:
  NiceGUI component: `Data Plotter` tab.
  Handler: web plotter VM + browser chart rendering.
  Status: Implemented (migrated in final stage).

