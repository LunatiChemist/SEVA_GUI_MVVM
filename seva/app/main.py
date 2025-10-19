# seva/app/main.py
from __future__ import annotations
import logging
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import defaultdict
import time
from datetime import datetime, timezone
from tkinter import filedialog
from typing import Any, Dict, Set, Optional, Iterable, List, TYPE_CHECKING

# ---- Views (UI-only) ----
from .views.main_window import MainWindowView
from .views.well_grid_view import WellGridView
from .views.experiment_panel_view import ExperimentPanelView
from .views.run_overview_view import RunOverviewView
from .views.channel_activity_view import ChannelActivityView
from .views.settings_dialog import SettingsDialog
from .views.data_plotter import DataPlotter

# ---- ViewModels ----
from ..viewmodels.plate_vm import PlateVM
from ..viewmodels.experiment_vm import ExperimentVM
from ..viewmodels.progress_vm import ProgressVM
from ..viewmodels.settings_vm import SettingsVM
from ..viewmodels.live_data_vm import LiveDataVM

# ---- UseCases & Adapter ----
from ..usecases.start_experiment_batch import (
    StartBatchResult,
    StartExperimentBatch,
    WellValidationResult,
)
from ..usecases.validate_start_plan import ValidateStartPlan
from ..usecases.poll_group_status import PollGroupStatus
from ..usecases.download_group_results import DownloadGroupResults
from ..usecases.cancel_group import CancelGroup
from ..usecases.test_connection import TestConnection
from ..usecases.run_flow_coordinator import (
    FlowHooks,
    FlowTick,
    GroupContext,
    RunFlowCoordinator,
)
from ..adapters.job_rest import JobRestAdapter
from ..adapters.device_rest import DeviceRestAdapter
from ..adapters.storage_local import StorageLocal
from ..adapters.relay_mock import RelayMock
from ..usecases.save_plate_layout import SavePlateLayout
from ..usecases.load_plate_layout import LoadPlateLayout
from ..domain.ports import UseCaseError
from ..usecases.test_relay import TestRelay
from ..usecases.set_electrode_mode import SetElectrodeMode
from ..adapters.api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    ApiTimeoutError,
    extract_error_hint,
)
from ..utils import logging as logging_utils

if TYPE_CHECKING:
    from ..usecases.cancel_runs import CancelRuns

try:
    from ..usecases.cancel_runs import CancelRuns as _CancelRunsClass
except ImportError:
    _CancelRunsClass = None

logging_utils.configure_root()


class App:
    """Bootstrap: wire Views <-> ViewModels, REST adapter, and simple polling."""

    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        # Main window with toolbar callback wiring
        self.win = MainWindowView(
            on_submit=self._on_submit,
            on_cancel_group=self._on_cancel_group,
            on_save_layout=self._on_save_layout,
            on_load_layout=self._on_load_layout,
            on_open_settings=self._on_open_settings,
            on_open_data_plotter=self._on_open_plotter,
        )
        self._last_download_dir: Optional[str] = None
        self.win.bind("<Control-Shift-o>", self._on_open_download_folder_hotkey)
        self.win.bind("<Control-Shift-O>", self._on_open_download_folder_hotkey)

        # ---- ViewModels ----
        self.plate_vm = PlateVM(on_selection_changed=self._on_selection_changed)
        self.experiment_vm = ExperimentVM()
        self.progress_vm = ProgressVM(
            on_update_run_overview=self._apply_run_overview,
            on_update_channel_activity=self._apply_channel_activity,
        )
        self.settings_vm = SettingsVM()
        self.live_vm = LiveDataVM()

        # ---- Subviews (constructor callbacks; no .configure(...)) ----
        self.wellgrid = WellGridView(
            self.win.wellgrid_host,
            boxes=("A", "B", "C", "D"),
            on_select_wells=lambda sel: self.plate_vm.set_selection(sel),
            on_copy_params_from=lambda wid: self.plate_vm.cmd_copy_from(wid),
            on_paste_params_to_selection=self.plate_vm.cmd_paste_to_selection,
            on_toggle_enable_selected=self.plate_vm.cmd_toggle_enable_selection,
            on_reset_selected=self._on_reset_well_config,
            on_open_plot=lambda wid: self._open_plot_for_well(wid),
        )
        self.wellgrid.pack(fill="both", expand=True)
        self.win.mount_wellgrid(self.wellgrid)

        self.experiment = ExperimentPanelView(
            self.win.tab_experiment,
            on_change=lambda fid, val: self.experiment_vm.set_field(fid, val),
            on_toggle_control_mode=None,
            on_apply_params=self._on_apply_params,
            on_end_task=self._on_cancel_group,
            on_end_selection=self._on_end_selection,
            on_copy_cv=lambda: self._on_copy_mode("CV"),
            on_paste_cv=lambda: self._on_paste_mode("CV"),
            on_copy_dcac=lambda: self._on_copy_mode("DCAC"),
            on_paste_dcac=lambda: self._on_paste_mode("DCAC"),
            on_copy_cdl=lambda: self._on_copy_mode("CDL"),
            on_paste_cdl=lambda: self._on_paste_mode("CDL"),
            on_copy_eis=lambda: self._on_copy_mode("EIS"),
            on_paste_eis=lambda: self._on_paste_mode("EIS"),
            on_electrode_mode_changed=self._on_electrode_mode_changed,  # relay-only, not part of REST
        )
        self.win.mount_experiment_panel(self.experiment)

        self.run_overview = RunOverviewView(
            self.win.tab_run_overview,
            boxes=("A", "B", "C", "D"),
            on_cancel_group=self._on_cancel_group,
            on_download_group_results=self._on_download_group_results,
            on_download_box_results=self._on_download_box_results,
            on_open_plot=self._on_open_plotter,
        )
        self.win.mount_run_overview(self.run_overview)

        self.activity = ChannelActivityView(
            self.win.tab_channel_activity, boxes=("A", "B", "C", "D")
        )
        self.win.mount_channel_activity(self.activity)

        # ---- REST Adapter & UseCases (lazy init after settings) ----
        self._job_adapter: Optional[JobRestAdapter] = None
        self._device_adapter: Optional[DeviceRestAdapter] = None
        self.uc_start: Optional[StartExperimentBatch] = None
        self.uc_validate_start_plan: Optional[ValidateStartPlan] = None
        self.uc_poll: Optional[PollGroupStatus] = None
        self.uc_download: Optional[DownloadGroupResults] = None
        self.uc_cancel: Optional[CancelGroup] = None
        self.uc_cancel_runs: Optional['CancelRuns'] = None
        self.uc_test_connection: Optional[TestConnection] = None

        # ---- Download metadata per group ----
        self._group_storage_meta: Dict[str, Dict[str, str]] = {}

        # ---- LocalStorage Adapter ----
        self._storage_root = os.environ.get("SEVA_STORAGE_ROOT") or "."
        self._storage = StorageLocal(root_dir=self._storage_root)
        self._load_user_settings()

        self.uc_save_layout = SavePlateLayout(self._storage)
        self.uc_load_layout = LoadPlateLayout(self._storage)

        # ---- Relay Adapter & UseCases ----
        self._relay = RelayMock()
        self.uc_test_relay = TestRelay(self._relay)
        self.uc_set_electrode_mode = SetElectrodeMode(self._relay)

        # ---- Run flow coordinator wiring ----
        self._current_group_id: Optional[str] = None
        self._flow_ctx: Optional[GroupContext] = None
        self._coordinator: Optional[RunFlowCoordinator] = None
        self._flow_hooks = FlowHooks(
            on_started=self._on_flow_started,
            on_snapshot=self._on_flow_snapshot,
            on_completed=self._on_flow_completed,
            on_error=self._on_flow_error,
            on_validation_errors=self._handle_start_validations,
        )
        self._poll_after_id: Optional[str] = None

        # ---- Initial UI state (demo-ish) ----
        self._seed_demo_state()
        self.win.set_status_message("Ready.")

    def _load_user_settings(self) -> None:
        payload: Optional[Dict] = None
        try:
            payload = self._storage.load_user_settings()
        except Exception as exc:
            self.win.show_toast(f"Could not load settings: {exc}")
        if payload is not None:
            try:
                self.settings_vm.apply_dict(payload)
            except ValueError as exc:
                self.win.show_toast(str(exc))
        self._apply_logging_preferences()

    def _apply_logging_preferences(self) -> None:
        level = logging_utils.apply_gui_preferences(self.settings_vm.debug_logging)
        self._log.debug(
            "Effective GUI log level: %s", logging_utils.level_name(level)
        )

    # ==================================================================
    # Adapter wiring
    # ==================================================================
    def _ensure_adapter(self) -> bool:
        """Build the REST adapter and use cases from SettingsVM if not yet present."""
        if (
            self._job_adapter
            and self._device_adapter
            and (self.uc_cancel_runs or _CancelRunsClass is None)
        ):
            return True

        base_urls = {k: v for k, v in (self.settings_vm.box_urls or {}).items() if v}
        if not base_urls:
            self.win.show_toast("Configure box URLs in Settings first.")
            return False

        api_keys = {k: v for k, v in (self.settings_vm.api_keys or {}).items() if v}
        if self._job_adapter is None:
            self._job_adapter = JobRestAdapter(
                base_urls=base_urls,
                api_keys=api_keys,
                request_timeout_s=self.settings_vm.request_timeout_s,
                download_timeout_s=self.settings_vm.download_timeout_s,
                retries=2,
            )
            self.uc_poll = PollGroupStatus(self._job_adapter)
            self.uc_download = DownloadGroupResults(self._job_adapter)
            self.uc_cancel = CancelGroup(self._job_adapter)

        if _CancelRunsClass and self._job_adapter and self.uc_cancel_runs is None:
            self.uc_cancel_runs = _CancelRunsClass(self._job_adapter)

        if self._device_adapter is None:
            self._device_adapter = DeviceRestAdapter(
                base_urls=base_urls,
                api_keys=api_keys,
                request_timeout_s=self.settings_vm.request_timeout_s,
                retries=2,
            )

        if self._job_adapter and self._device_adapter:
            self.uc_start = StartExperimentBatch(
                self._job_adapter, self._device_adapter
            )
            self.uc_validate_start_plan = ValidateStartPlan(self._device_adapter)
            self.uc_test_connection = TestConnection(self._device_adapter)
        if self._job_adapter and self._device_adapter:
            self._ensure_coordinator()
        return True

    def _ensure_coordinator(self) -> bool:
        """Instantiate the RunFlowCoordinator when all dependencies are ready."""
        if self._coordinator:
            return True
        if not (
            self._job_adapter
            and self._device_adapter
            and self.uc_validate_start_plan
            and self.uc_start
            and self.uc_poll
            and self.uc_download
        ):
            return False

        self._coordinator = RunFlowCoordinator(
            job_port=self._job_adapter,
            device_port=self._device_adapter,
            storage_port=self._storage,
            uc_validate_start=self.uc_validate_start_plan,
            uc_start=self.uc_start,
            uc_poll=self.uc_poll,
            uc_download=self.uc_download,
            settings=self.settings_vm,
            hooks=self._flow_hooks,
        )
        return True

    # ==================================================================
    # Demo data seeding (light)
    # ==================================================================
    def _seed_demo_state(self) -> None:
        self.wellgrid.set_boxes(("A", "B", "C", "D"))
        self.wellgrid.set_selection([])
        self.experiment.set_editing_well("–")
        self.experiment.set_electrode_mode("3E")
        # initial empty/idle overview
        self._apply_run_overview({"boxes": {}, "wells": [], "activity": {}})
        self.activity.set_updated_at("")

    # ==================================================================
    # Toolbar / Actions
    # ==================================================================
    def _on_submit(self) -> None:
        """Handle toolbar submit triggered by the user."""
        # Submit: validate plan and kick off coordinator flow.
        try:
            if not self._ensure_adapter() or not self._ensure_coordinator():
                return

            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("No configured wells to start.")
                return

            selection = self.plate_vm.get_selection()
            self.experiment_vm.set_selection(selection)
            plan = self._build_plan_from_vm(selection)
            boxes = sorted(
                {str(wid)[0] for wid in configured if isinstance(wid, str) and wid}
            )
            summary = {
                "wells": len(configured),
                "boxes": boxes or ["-"],
                "stream": bool(self.settings_vm.use_streaming),
            }
            self._log.info("Submitting start request: %s", summary)
            self._log.debug("Start selection=%s", sorted(configured))

            validations = self._coordinator.validate(plan)  # type: ignore[arg-type]
            has_invalid = any(not entry.ok for entry in validations)
            has_warnings = any(entry.ok and entry.warnings for entry in validations)
            if has_invalid or has_warnings:
                self._flow_hooks.on_validation_errors(validations)
            if has_invalid:
                self.win.show_toast("No runs started. Fix validation errors.")
                return

            plan["all_or_nothing"] = True

            ctx = self._coordinator.start(plan)  # type: ignore[arg-type]
            start_result = self._coordinator.last_start_result()
            if not isinstance(start_result, StartBatchResult):
                raise RuntimeError("Coordinator returned an unexpected start result.")

            if start_result.validations != validations:
                self._flow_hooks.on_validation_errors(start_result.validations)

            if not start_result.run_group_id:
                if not start_result.started_wells:
                    self.win.show_toast("No runs started. Fix validation errors.")
                else:
                    self.win.show_toast(
                        "Validation stopped some wells. Nothing started."
                    )
                self._coordinator.stop_polling()
                self._flow_ctx = None
                return

            group_id = start_result.run_group_id
            subruns = start_result.per_box_runs
            storage_payload = plan.get("storage") or {}
            normalized_storage = {
                "experiment": str(storage_payload.get("experiment_name") or "").strip(),
                "subdir": str(storage_payload.get("subdir") or "").strip(),
                "client_datetime": str(storage_payload.get("client_datetime") or "").strip(),
                "results_dir": str(
                    storage_payload.get("results_dir") or self.settings_vm.results_dir or ""
                ).strip()
                or self.settings_vm.results_dir,
            }
            self._group_storage_meta[group_id] = normalized_storage
            self._log.info(
                "Start response: group=%s wells=%d boxes=%s",
                group_id,
                len(start_result.started_wells),
                sorted(subruns.keys()),
            )
            self._log.debug("Start run map: %s", subruns)

            self._current_group_id = group_id
            self._flow_ctx = ctx
            self.win.set_run_group_id(group_id)

            started_boxes = ", ".join(sorted(subruns.keys()))
            skipped = sum(1 for entry in start_result.validations if not entry.ok)
            started_count = len(start_result.started_wells)
            if skipped:
                self.win.show_toast(
                    f"Started group {group_id} ({started_count} wells, skipped {skipped})."
                )
            else:
                if started_boxes:
                    self.win.show_toast(f"Started group {group_id} on {started_boxes}")
                else:
                    self.win.show_toast(f"Started group {group_id}.")

            self.wellgrid.add_configured_wells(start_result.started_wells)

            self._cancel_poll_timer()
            self._on_poll_tick()
        except Exception as e:
            self._stop_polling()
            self._current_group_id = None
            self._toast_error(e)
    def _on_cancel_group(self) -> None:
        if not self._current_group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        try:
            current = self._current_group_id
            self._log.info("Cancel requested for group %s", current)
            self.uc_cancel(current)  # prints notice in adapter
            self._stop_polling()
            self._current_group_id = None
            self.win.set_run_group_id("")        # optional UI cleanup
            self.win.show_toast("Cancel requested (API not implemented).")
        except Exception as e:
            self._toast_error(e)

    def _on_end_selection(self) -> None:
        selection = sorted(self.plate_vm.get_selection())
        if not selection:
            self.win.show_toast("Select at least one well.")
            return
        if not self._ensure_adapter():
            return
        cancel_runs = self.uc_cancel_runs
        if cancel_runs is None:
            self.win.show_toast("Cancel selected runs not available.")
            return

        selected = set(selection)
        box_to_runs: Dict[str, Set[str]] = defaultdict(set)

        snapshot = self.progress_vm.last_snapshot
        if snapshot:
            for well_id, status in snapshot.runs.items():
                well_token = str(well_id).strip()
                if well_token not in selected:
                    continue
                run_id = str(status.run_id).strip()
                if not run_id:
                    continue
                box_id = self._box_prefix_from_well(well_token)
                if not box_id:
                    continue
                box_to_runs[box_id].add(run_id)

        payload = {box: sorted(runs) for box, runs in box_to_runs.items() if runs}
        if not payload:
            self.win.show_toast("Selected wells have no active runs.")
            return

        try:
            self._log.info(
                "End selection requested for wells: %s", ", ".join(selection)
            )
            request = {"box_runs": payload, "span": "selected"}
            cancel_runs(request)
            self.win.show_toast("Abort requested for selected runs.")
        except Exception as exc:
            self._toast_error(exc, context="Cancel runs")

    @staticmethod
    def _box_prefix_from_well(well_id: str) -> Optional[str]:
        token = ""
        for ch in well_id:
            if ch.isalpha():
                token += ch
            else:
                break
        return token.upper() or None

    def _on_save_layout(self) -> None:
        try:
            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("Nothing to save: no configured wells.")
                return
            well_map = self.experiment_vm.build_well_params_map(configured)
            default_name = f"layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            initial_dir = os.path.abspath(self._storage_root)
            if not os.path.isdir(initial_dir):
                initial_dir = os.getcwd()
            path = filedialog.asksaveasfilename(
                parent=self.win,
                defaultextension=".json",
                filetypes=[("Layout JSON", "layout_*.json")],
                initialfile=default_name,
                initialdir=initial_dir,
                title="Save Layout",
            )
            if not path:
                return
            saved_path = self.uc_save_layout(path, configured, well_map)  # type: ignore[misc]
            self.win.show_toast(f"Saved {saved_path.name}")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_load_layout(self) -> None:
        try:
            initial_dir = os.path.abspath(self._storage_root)
            if not os.path.isdir(initial_dir):
                initial_dir = os.getcwd()
            path = filedialog.askopenfilename(
                parent=self.win,
                filetypes=[("Layout JSON", "layout_*.json")],
                initialdir=initial_dir,
                title="Load Layout",
            )
            if not path:
                return
            data = self.uc_load_layout(path)  # type: ignore[misc]
            raw_map = data.get("well_params_map") or {}
            wmap: Dict[str, Dict[str, str]] = {}
            if isinstance(raw_map, dict):
                for wid, snapshot in raw_map.items():
                    wid_str = str(wid)
                    if isinstance(snapshot, dict):
                        wmap[wid_str] = dict(snapshot)
                    else:
                        wmap[wid_str] = {}
            selection_raw = data.get("selection")
            wells_list: List[str] = []
            if isinstance(selection_raw, list):
                for item in selection_raw:
                    wid = str(item)
                    if wid not in wells_list:
                        wells_list.append(wid)
            elif isinstance(selection_raw, str):
                wells_list = [selection_raw]
            if not wells_list:
                wells_list = sorted(wmap.keys())
            self.experiment_vm.well_params.clear()
            for wid, snap in wmap.items():
                self.experiment_vm.save_params_for(wid, snap)
            configured_wells = set(wmap.keys()) or set(wells_list)
            self.plate_vm.clear_all_configured()
            self.plate_vm.mark_configured(configured_wells)
            self.wellgrid.set_configured_wells(configured_wells)
            if wells_list:
                first_well = wells_list[0]
                self.experiment_vm.set_selection({first_well})
                self.experiment_vm.fields = dict(wmap.get(first_well, {}))
                self.wellgrid.set_selection([first_well])
            else:
                self.experiment_vm.set_selection(set())
            self.win.show_toast(f"Loaded {os.path.basename(path)}")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_open_settings(self) -> None:
        dlg: Optional[SettingsDialog] = None

        def handle_test_connection(box_id: str) -> None:
            if not dlg:
                return
            url_var = dlg.url_vars.get(box_id)
            if url_var is None:
                self.win.show_toast(f"Box {box_id}: not available.")
                return
            base_url = url_var.get().strip()
            if not base_url:
                self.win.show_toast(f"Box {box_id}: URL required for test.")
                return

            api_key_var = dlg.key_vars.get(box_id)
            api_key = api_key_var.get().strip() if api_key_var else ""
            request_timeout = SettingsDialog._parse_int(
                dlg.request_timeout_var.get(), self.settings_vm.request_timeout_s
            )

            device_port: Optional[DeviceRestAdapter] = None
            uc: Optional[TestConnection] = None

            adapter = self._device_adapter
            if adapter is None:
                saved_url = (self.settings_vm.box_urls or {}).get(box_id, "").strip()
                if saved_url:
                    if self._ensure_adapter():
                        adapter = self._device_adapter
            if adapter and getattr(adapter, "base_urls", {}).get(box_id) == base_url:
                device_port = adapter
                uc = self.uc_test_connection
                if uc is None:
                    uc = TestConnection(device_port)
                    self.uc_test_connection = uc

            if device_port is None or uc is None:
                api_map = {box_id: api_key} if api_key else {}
                device_port = DeviceRestAdapter(
                    base_urls={box_id: base_url},
                    api_keys=api_map,
                    request_timeout_s=request_timeout,
                    retries=0,
                )
                uc = TestConnection(device_port)

            assert uc is not None
            try:
                result = uc(box_id)
            except UseCaseError as err:
                reason = err.message or str(err)
                self.win.show_toast(f"Box {box_id}: failed ({reason})")
                return
            except Exception as exc:
                self._toast_error(exc, context=f"Box {box_id}")
                return

            status = "ok" if result.get("ok") else "failed"
            devices = result.get("device_count")
            device_text = (
                f"devices={devices}" if devices is not None else "devices=?"
            )
            health = result.get("health") or {}
            reason = str(
                health.get("message")
                or health.get("detail")
                or health.get("error")
                or ""
            ).strip()
            detail = device_text if status == "ok" else (reason or device_text)
            self.win.show_toast(f"Box {box_id}: {status} ({detail})")

        def handle_test_relay() -> None:
            if not dlg:
                return
            ip = dlg.relay_ip_var.get().strip()
            port_raw = dlg.relay_port_var.get().strip()
            if not ip:
                self.win.show_toast("Relay IP required for test.")
                return
            if not port_raw:
                self.win.show_toast("Relay port required for test.")
                return
            try:
                port = int(port_raw)
            except ValueError:
                self.win.show_toast("Relay port must be an integer.")
                return
            try:
                ok = self.uc_test_relay(ip, port)
            except Exception as e:
                self.win.show_toast(str(e))
                return
            message = "Relay test successful." if ok else "Relay test failed."
            self.win.show_toast(message)

        def handle_browse_results_dir() -> None:
            if not dlg:
                return
            current = dlg.results_dir_var.get().strip()
            if not current:
                current = self.settings_vm.results_dir or "."
            initial_dir = current
            if initial_dir and not os.path.isdir(initial_dir):
                home_dir = os.path.expanduser("~")
                initial_dir = home_dir if os.path.isdir(home_dir) else ""
            try:
                selected = filedialog.askdirectory(
                    parent=dlg,
                    initialdir=initial_dir or None,
                    title="Select Results Directory",
                )
            except Exception as exc:
                self.win.show_toast(f"Could not open folder picker: {exc}")
                return
            if not selected:
                return
            new_dir = os.path.normpath(selected)
            self.settings_vm.set_results_dir(new_dir)
            dlg.set_results_dir(new_dir)

        dlg = SettingsDialog(
            self.win,
            on_test_connection=handle_test_connection,
            on_test_relay=handle_test_relay,
            on_browse_results_dir=handle_browse_results_dir,
            on_save=self._on_settings_saved,
            on_close=lambda: None,
        )
        # Populate dialog from VM
        dlg.set_box_urls(self.settings_vm.box_urls)
        dlg.set_api_keys(self.settings_vm.api_keys)
        dlg.set_timeouts(
            self.settings_vm.request_timeout_s, self.settings_vm.download_timeout_s
        )
        dlg.set_poll_interval(self.settings_vm.poll_interval_ms)
        dlg.set_results_dir(self.settings_vm.results_dir)
        dlg.set_experiment_name(self.settings_vm.experiment_name)
        dlg.set_subdir(self.settings_vm.subdir)
        dlg.set_use_streaming(self.settings_vm.use_streaming)
        dlg.set_debug_logging(self.settings_vm.debug_logging)
        dlg.set_relay_config(self.settings_vm.relay_ip, self.settings_vm.relay_port)
        dlg.set_save_enabled(self.settings_vm.is_valid())

    def _on_settings_saved(self, cfg: dict) -> None:
        payload = dict(cfg or {})
        raw_dir = str(payload.get("results_dir") or ".").strip() or "."
        expanded_dir = os.path.expanduser(raw_dir)
        target_dir = os.path.abspath(expanded_dir)

        if not os.path.isdir(target_dir):
            self.win.show_toast(f"Results directory does not exist: {raw_dir}")
            return

        tmp_fd: Optional[int] = None
        tmp_path: str = ""
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=target_dir, prefix="seva_results_dir_", suffix=".tmp"
            )
            os.close(tmp_fd)
            tmp_fd = None
            os.remove(tmp_path)
            tmp_path = ""
        except Exception as exc:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            self.win.show_toast(f"Results directory not writable: {exc}")
            return

        payload["results_dir"] = os.path.normpath(expanded_dir)

        try:
            self.settings_vm.apply_dict(payload)
            self._storage.save_user_settings(self.settings_vm.to_dict())
            self._apply_logging_preferences()
        except Exception as exc:
            self.win.show_toast(f"Could not save settings: {exc}")
            return

        # reset adapter to reflect new settings
        self._stop_polling()
        self._job_adapter = None
        self._device_adapter = None
        self.uc_test_connection = None
        self._coordinator = None
        self._flow_ctx = None
        self._poll_after_id = None
        self.win.show_toast("Settings saved.")

    def _on_open_plotter(self) -> None:
        dp = DataPlotter(
            self.win,
            on_fetch_data=lambda: self.win.show_toast("Fetch (not wired)"),
            on_axes_changed=lambda x, y: self.win.show_toast(f"Axes: {x}/{y}"),
            on_section_changed=lambda s: self.win.show_toast(f"Section: {s}"),
            on_apply_ir=lambda rs: self.win.show_toast(f"Apply IR Rs={rs}"),
            on_reset_ir=lambda: self.win.show_toast("Reset IR"),
            on_export_csv=lambda: self.win.show_toast("Export CSV (not wired)"),
            on_export_png=lambda: self.win.show_toast("Export PNG (not wired)"),
            on_open_plot=lambda wid: self._open_plot_for_well(wid),
            on_open_results_folder=lambda wid: self.win.show_toast(
                f"Open folder for {wid}"
            ),
            on_toggle_include=lambda wid, inc: self.win.show_toast(
                f"{'Include' if inc else 'Exclude'} {wid}"
            ),
            on_close=lambda: None,
        )
        selection_summary = ", ".join(sorted(self.plate_vm.get_selection())) or "–"
        dp.set_run_info(self._current_group_id or "—", selection_summary)

    def _on_download_group_results(self) -> None:
        group_id = self._current_group_id
        if not group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        storage_meta = self._group_storage_meta.get(group_id)
        if not storage_meta:
            self.win.show_toast(
                "Missing storage metadata for the active group. Start must finish before downloading."
            )
            return
        results_dir = storage_meta.get("results_dir") or self.settings_vm.results_dir
        if not results_dir:
            self.win.show_toast("Results directory is not configured for downloads.")
            return
        try:
            out_dir = self.uc_download(
                group_id,
                results_dir,
                storage_meta,
                cleanup="archive",
            )  # type: ignore[misc]
            self._log.info(
                "Downloaded group %s to %s", group_id, out_dir
            )
            resolved_dir = os.path.abspath(out_dir)
            self._last_download_dir = resolved_dir
            self.win.show_toast(self._build_download_toast(group_id, resolved_dir))
        except Exception as e:
            self._toast_error(e)

    def _on_download_box_results(self, box_id: str) -> None:
        # Group ZIPs are per group; per-box filtering could be added in adapter if needed
        self._on_download_group_results()

    def _build_download_toast(self, group_id: str, path: str) -> str:
        short_path = self._shorten_download_path(path)
        descriptor = ""
        meta = self._group_storage_meta.get(group_id) if group_id else None
        if meta:
            parts = [
                str(meta.get("experiment") or "").strip(),
                str(meta.get("subdir") or "").strip(),
                str(meta.get("client_datetime") or "").strip(),
            ]
            descriptor = "/".join([p for p in parts if p])
        target = f"{descriptor} → {short_path}" if descriptor else short_path
        if self._can_open_results_folder():
            return f"Results unpacked to {target} (Ctrl+Shift+O to open)"
        return f"Results unpacked to {target}"

    def _shorten_download_path(self, path: str, max_len: int = 60) -> str:
        normalized = os.path.normpath(path)
        if len(normalized) <= max_len:
            return normalized
        suffix_len = max(3, max_len - 3)
        return f"...{normalized[-suffix_len:]}"

    def _can_open_results_folder(self) -> bool:
        if sys.platform.startswith("win"):
            return hasattr(os, "startfile")
        if sys.platform == "darwin":
            return True
        return shutil.which("xdg-open") is not None

    def _on_open_download_folder_hotkey(self, event=None):
        if not self._last_download_dir:
            self.win.show_toast("Nothing downloaded yet.")
            return "break"
        if not self._can_open_results_folder():
            self.win.show_toast("Open folder not supported on this platform.")
            return "break"
        self._open_results_folder(self._last_download_dir)
        return "break"

    def _open_results_folder(self, path: str) -> None:
        """Open the download folder using the platform default file browser."""
        if not path or not os.path.isdir(path):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                opener = shutil.which("xdg-open")
                if not opener:
                    raise RuntimeError("xdg-open not available")
                subprocess.Popen([opener, path])
        except Exception as exc:
            self.win.show_toast(f"Could not open folder: {exc}")

    # ==================================================================
    # VM ↔ View glue
    # ==================================================================
    def _on_selection_changed(self, sel: Set[str]) -> None:
        # Show saved params if exactly one well selected
        if len(sel) == 1:
            wid = next(iter(sel))
            params = self.experiment_vm.get_params_for(wid)
            if params:
                self.experiment.set_fields(params)
            else:
                self.experiment.clear_fields()
        else:
            # For multi-select or none: clear fields
            self.experiment.clear_fields()

    def _on_apply_params(self) -> None:
        selection = self.plate_vm.get_selection()
        if not selection:
            self.win.show_toast("No wells selected.")
            return

        # Save params for each selected well
        for wid in selection:
            self.experiment_vm.save_params_for(wid, self.experiment_vm.fields)

        # Mark selected wells as configured
        self.plate_vm.mark_configured(selection)
        self.wellgrid.add_configured_wells(selection)

        self.win.show_toast("Parameters applied.")

    def _on_reset_well_config(self) -> None:
        selection = self.plate_vm.get_selection()
        if not selection:
            self.win.show_toast("No wells selected.")
            return

        for wid in selection:
            self.experiment_vm.clear_params_for(wid)

        self.plate_vm.clear_configured(selection)
        self.wellgrid.clear_configured_wells(selection)
        self._on_selection_changed(selection)
        self.win.show_toast("Well config reset.")

    def _mode_label(self, mode: str) -> str:
        return {
            "CV": "CV",
            "DCAC": "DC/AC",
            "CDL": "CDL",
            "EIS": "EIS",
        }.get((mode or "").upper(), mode)

    def _on_copy_mode(self, mode: str) -> None:
        selection = self.plate_vm.get_selection()
        if len(selection) == 0:
            self.win.show_toast("Select one well to copy.")
            return
        if len(selection) > 1:
            self.win.show_toast("Select exactly one well to copy.")
            return
        well_id = next(iter(selection))
        try:
            snapshot = self.experiment_vm.build_mode_snapshot_for_copy(mode)
        except Exception as e:
            self.win.show_toast(str(e))
            return
        if not snapshot:
            self.win.show_toast("No params in form.")
            return
        try:
            self.experiment_vm.cmd_copy_mode(mode, well_id, source_snapshot=snapshot)
            self.win.show_toast(f"Copied {self._mode_label(mode)}.")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_paste_mode(self, mode: str) -> None:
        selection = self.plate_vm.get_selection()
        if not selection:
            self.win.show_toast("No wells selected.")
            return

        clipboard_attr = {
            "CV": "clipboard_cv",
            "DCAC": "clipboard_dcac",
            "CDL": "clipboard_cdl",
            "EIS": "clipboard_eis",
        }.get((mode or "").upper())
        clipboard = getattr(self.experiment_vm, clipboard_attr, {})
        if not clipboard:
            self.win.show_toast("Clipboard empty.")
            return

        try:
            self.experiment_vm.cmd_paste_mode(mode, selection)
        except Exception as e:
            self.win.show_toast(str(e))
            return

        self.plate_vm.mark_configured(selection)
        self.wellgrid.add_configured_wells(selection)
        self._on_selection_changed(selection)
        self.win.show_toast(f"Pasted {self._mode_label(mode)}.")

    def _on_electrode_mode_changed(self, mode: str) -> None:
        try:
            self.experiment_vm.set_electrode_mode(mode)
            self.uc_set_electrode_mode(mode)
            self.win.show_toast(f"Electrode mode: {mode}")
        except Exception as e:
            self.win.show_toast(str(e))

    def _apply_run_overview(self, dto: Dict) -> None:
        boxes = dto.get("boxes", {}) or {}
        for b, meta in boxes.items():
            # subrun may be a CSV string or a list; normalize to CSV for the view
            sub = meta.get("subrun")
            if isinstance(sub, list):
                sub = ", ".join(sub)
            self.run_overview.set_box_status(
                b,
                phase=meta.get("phase", "Idle"),
                progress_pct=meta.get("progress", 0),
                sub_run_id=sub,
            )
        self.run_overview.set_well_rows(dto.get("wells", []) or [])
        self._apply_channel_activity(dto.get("activity", {}) or {})

    def _apply_channel_activity(self, mapping: Dict[str, str]) -> None:
        self.activity.set_activity(mapping)
        now_str = time.strftime("%H:%M:%S")
        self.activity.set_updated_at(f"Updated at {now_str}")

    def _open_plot_for_well(self, well_id: str) -> None:
        self.win.show_toast(f"Open PNG for {well_id}")

    # ==================================================================
    # Polling helpers
    # ==================================================================
    def _stop_polling(self) -> None:
        """Cancel any scheduled poll and mark the coordinator inactive."""
        self._cancel_poll_timer()
        if self._coordinator:
            self._coordinator.stop_polling()
        self._flow_ctx = None

    def _cancel_poll_timer(self) -> None:
        if self._poll_after_id is not None:
            try:
                self.win.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None

    def _schedule_poll(self, delay_ms: int) -> None:
        delay = max(1, int(delay_ms))
        self._cancel_poll_timer()
        self._poll_after_id = self.win.after(delay, self._on_poll_tick)

    def _on_poll_tick(self) -> None:
        """Cooperative poll tick executed on the Tkinter thread."""
        # PollTick: request snapshot and schedule next tick when advised.
        if not self._flow_ctx or not self._coordinator:
            return
        if not self._ensure_adapter() or not self._ensure_coordinator():
            return

        tick: FlowTick = self._coordinator.poll_once(self._flow_ctx)
        if tick.event == "tick":
            delay = tick.next_delay_ms
            if delay is None:
                base = getattr(self.settings_vm, "poll_interval_ms", 1000) or 1000
                try:
                    delay = max(200, int(base))
                except (TypeError, ValueError):
                    delay = 1000
            self._schedule_poll(int(delay))
            return

        # Completed/Error: no further scheduling; rely on hooks for UI feedback.
        self._cancel_poll_timer()
        if tick.event == "completed":
            self._coordinator.stop_polling()
            auto_download_enabled = getattr(
                self.settings_vm, "auto_download_on_complete", True
            )
            download_path: Optional[Path] = None
            if tick.snapshot and self._flow_ctx:
                try:
                    download_path = self._coordinator.on_completed(
                        self._flow_ctx, tick.snapshot
                    )
                except Exception as exc:
                    self._flow_ctx = None
                    self._toast_error(exc, context="Download failed")
                    return
            if not auto_download_enabled:
                self._on_flow_completed(None)
            self._flow_ctx = None
            return

        if tick.event == "error":
            self._coordinator.stop_polling()
            self._flow_ctx = None

    def _on_flow_started(self, ctx: GroupContext) -> None:
        """Hook fired when the coordinator successfully starts a group."""
        self._log.debug("Coordinator acknowledged start for group %s", ctx.group)

    def _on_flow_snapshot(self, snapshot) -> None:
        """Hook fired on every polling snapshot."""
        if snapshot:
            self.progress_vm.apply_snapshot(snapshot)

    def _on_flow_completed(self, path: Optional[Path] = None) -> None:
        """Hook fired when the flow reports completion."""
        if path:
            resolved_dir = os.path.abspath(str(path))
            self._last_download_dir = resolved_dir
            group_id = self._current_group_id
            if group_id:
                self.win.show_toast(
                    self._build_download_toast(group_id, resolved_dir)
                )
            else:
                short_path = self._shorten_download_path(resolved_dir)
                if self._can_open_results_folder():
                    self.win.show_toast(
                        f"Results unpacked to {short_path} (Ctrl+Shift+O to open)"
                    )
                else:
                    self.win.show_toast(f"Results unpacked to {short_path}")
            return
        self.win.show_toast("All runs completed.")

    def _on_flow_error(self, message: str) -> None:
        """Hook fired when the flow reports a polling error."""
        text = message.strip() if isinstance(message, str) else ""
        if text:
            self._log.error("Polling error: %s", text)
        else:
            self._log.error("Polling error: <empty message>")
        self.win.show_toast(text or "Polling failed.")

    # ==================================================================
    # Error handling helpers
    # ==================================================================

    def _toast_error(self, err: Exception, *, context: Optional[str] = None) -> None:
        message = self._format_error_message(err)
        if context:
            message = f"{context}: {message}"
        self.win.show_toast(message)

    def _format_error_message(self, err: Exception) -> str:
        if isinstance(err, UseCaseError):
            self._log.warning("UseCase error (%s): %s", err.code, err.message)
            return err.message
        if isinstance(err, ApiTimeoutError):
            self._log.warning("API timeout (%s)", getattr(err, "context", ""))
            return "Request timed out. Check connection."
        if isinstance(err, ApiClientError):
            status = err.status or 0
            hint = err.hint or extract_error_hint(getattr(err, "payload", None))
            if status == 422:
                return self._compose_error_message("Invalid parameters", hint)
            if status == 409:
                slot = self._extract_slot_hint(err) or hint
                return self._compose_error_message("Slot busy", slot)
            if status in (401, 403):
                return "Auth failed / API key invalid."
            label = f"Request failed (HTTP {status})" if status else "Request failed"
            return self._compose_error_message(label, hint)
        if isinstance(err, ApiServerError):
            self._log.error(
                "Server error while calling box (%s)", getattr(err, "context", "")
            )
            return "Box error, try again."
        if isinstance(err, ApiError):
            self._log.warning("API error (%s): %s", getattr(err, "context", ""), err)
            return str(err)
        self._log.exception("Unexpected error")
        return str(err)

    def _compose_error_message(self, base: str, hint: Optional[str]) -> str:
        hint_text = (hint or "").strip()
        if hint_text:
            return f"{base}: {hint_text}"
        if base.endswith("."):
            return base
        return f"{base}."

    def _extract_slot_hint(self, err: ApiClientError) -> Optional[str]:
        payload = getattr(err, "payload", None)
        slot = self._find_slot(payload)
        if slot:
            return slot
        hint = err.hint or extract_error_hint(payload)
        if hint:
            cleaned = hint.replace(",", " ").replace(";", " ")
            for token in cleaned.split():
                lower = token.lower()
                if lower.startswith("slot"):
                    parts = token.split("=", 1)
                    return parts[1] if len(parts) == 2 else token
        return None

    def _find_slot(self, data: Any) -> Optional[str]:
        if isinstance(data, dict):
            for key in ("slot", "slot_id", "well", "well_id"):
                value = data.get(key)
                if value:
                    return str(value)
            for value in data.values():
                slot = self._find_slot(value)
                if slot:
                    return slot
        elif isinstance(data, list):
            for item in data:
                slot = self._find_slot(item)
                if slot:
                    return slot
        return None

    def _handle_start_validations(
        self, validations: Iterable[WellValidationResult]
    ) -> None:
        entries = list(validations)
        if not entries:
            return

        invalid = [entry for entry in entries if not entry.ok]
        warning_candidates = [
            entry for entry in entries if entry.ok and entry.warnings
        ]

        def _summarize(
            entries: List[WellValidationResult], attr: str
        ) -> str:
            snippets: List[str] = []
            for entry in entries:
                issues = getattr(entry, attr)
                if not issues:
                    continue
                parts: List[str] = []
                for issue in issues:
                    if not isinstance(issue, dict):
                        continue
                    field = str(issue.get("field", "") or "*")
                    code = str(issue.get("code", "issue"))
                    parts.append(f"{field}:{code}")
                if not parts:
                    continue
                snippets.append(f"{entry.well_id} ({entry.mode}): {', '.join(parts)}")
            if not snippets:
                return ""
            preview = "; ".join(snippets[:3])
            if len(snippets) > 3:
                preview += f"; +{len(snippets) - 3} more"
            return preview

        if invalid:
            summary = _summarize(invalid, "errors")
            message = (
                f"Validation blocked wells: {summary}"
                if summary
                else "Validation blocked wells."
            )
            self.win.show_toast(message)

        if warning_candidates:
            summary = _summarize(warning_candidates, "warnings")
            if summary:
                self.win.show_toast(f"Validation warnings: {summary}")

    # ==================================================================
    # Plan building
    # ==================================================================

    @staticmethod
    def _local_dt_slug() -> str:
        """Return a slug-safe timestamp based on the local timezone."""
        return datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S")

    @staticmethod
    def _slug(value: str) -> str:
        """Normalize text to a lowercase slug with underscores."""
        text = str(value or "").lower()
        cleaned = re.sub(r"[^a-z0-9_]+", "_", text)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned

    def _current_client_datetime(self) -> str:
        """Return a UTC timestamp suitable for the client_datetime payload."""
        timestamp = datetime.now().replace(microsecond=0)
        return timestamp.isoformat().replace(":", "-").replace("+00:00", "Z")

    def _build_storage_metadata(self) -> Dict[str, str]:
        """Collect experiment storage metadata from settings and transient overrides."""
        experiment_name = (self.settings_vm.experiment_name or "").strip()
        if not experiment_name:
            raise RuntimeError("Experiment name must be set in Settings.")
        subdir = (self.settings_vm.subdir or "").strip()
        override_dt = (
            self.experiment_vm.fields.get("storage.client_datetime")
            if hasattr(self.experiment_vm, "fields")
            else None
        )
        client_datetime = str(override_dt).strip() if override_dt else ""
        if not client_datetime:
            client_datetime = self._current_client_datetime()
        storage = {
            "experiment_name": experiment_name,
            "subdir": subdir,
            "client_datetime": client_datetime,
            "results_dir": self.settings_vm.results_dir,
        }
        return storage

    def _build_plan_from_vm(self, selection: Iterable[str]) -> Dict:
        """
        Build a JobRequest-ready plan for StartExperimentBatch.
        Collects all configured wells and their stored parameters.

        The UseCase will:
        - Route each configured well to its box prefix,
        - Generate one JobRequest per well.

        Fields tia_gain / sampling_interval are set to None for now
        until they are exposed in the Settings UI.
        """
        # 1) Always start from all configured wells (not just the active selection)
        configured = self.plate_vm.configured()
        if not configured:
            raise RuntimeError("No configured wells to start.")

        # 2) Gather persisted parameters for those wells
        well_params_map = self.experiment_vm.build_well_params_map(configured)
        if not well_params_map:
            raise RuntimeError("No saved parameters found for configured wells.")

        # 3) Optional global settings / defaults
        make_plot = False  # default: let backend create plots
        tia_gain = None  # will be added later via Settings
        sampling_interval = None  # will be added later via Settings

        # 4) Compose plan dict for the UseCase
        storage_meta = self._build_storage_metadata()
        plan = {
            "selection": sorted(configured),
            "well_params_map": well_params_map,
            "make_plot": make_plot,
            "tia_gain": tia_gain,
            "sampling_interval": sampling_interval,
            "storage": storage_meta,
            # group_id is injected below
        }

        # 5) Debug convenience (optional)
        boxes = sorted(
            {str(wid)[0] for wid in configured if isinstance(wid, str) and wid}
        )
        self._log.debug(
            "Built plan for %d wells across boxes %s",
            len(configured),
            ", ".join(boxes) if boxes else "-",
        )

        experiment_slug = self._slug(storage_meta.get("experiment_name") or "exp")
        if not experiment_slug:
            experiment_slug = "exp"
        subdir_slug = self._slug(storage_meta.get("subdir") or "")
        datetime_slug = self._slug(self._local_dt_slug())
        rand_suffix = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=4)
        )
        parts = [
            experiment_slug,
            subdir_slug or None,
            datetime_slug,
            rand_suffix,
        ]
        plan["group_id"] = "grp_" + "__".join(filter(None, parts))

        return plan


def main() -> None:
    app = App()
    app.win.mainloop()


if __name__ == "__main__":
    main()
