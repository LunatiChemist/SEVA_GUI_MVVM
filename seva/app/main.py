# seva/app/main.py
from __future__ import annotations
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import time
from datetime import datetime
from urllib.parse import urlparse
from tkinter import filedialog, messagebox
from typing import Any, Dict, Set, Optional, List, TYPE_CHECKING

# ---- Views (UI-only) ----
from .views.main_window import MainWindowView
from .views.well_grid_view import WellGridView
from .views.experiment_panel_view import ExperimentPanelView
from .views.run_overview_view import RunOverviewView
from .views.channel_activity_view import ChannelActivityView
from .views.settings_dialog import SettingsDialog
from .dataplotter_standalone import DataProcessingGUI
from .nas_gui_smb import NASSetupGUI
from .views.discovery_results_dialog import DiscoveryResultsDialog
from .views.runs_panel_view import RunsPanelView

# ---- ViewModels ----
from ..viewmodels.plate_vm import PlateVM
from ..viewmodels.experiment_vm import ExperimentVM
from ..viewmodels.progress_vm import ProgressVM
from ..viewmodels.settings_vm import SettingsVM, BOX_IDS
from ..viewmodels.live_data_vm import LiveDataVM
from ..viewmodels.runs_vm import RunsVM

# ---- UseCases & Adapter ----
from .run_flow_presenter import RunFlowPresenter
from ..adapters.storage_local import StorageLocal
from ..adapters.discovery_http import HttpDiscoveryAdapter
from ..adapters.relay_mock import RelayMock
from ..usecases.save_plate_layout import SavePlateLayout
from ..usecases.load_plate_layout import LoadPlateLayout
from ..domain.runs_registry import RunsRegistry
from ..domain.ports import UseCaseError
from ..usecases.test_relay import TestRelay
from ..usecases.set_electrode_mode import SetElectrodeMode
from ..usecases.discover_devices import DiscoverDevices, MergeDiscoveredIntoRegistry
from ..adapters.api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    ApiTimeoutError,
    extract_error_hint,
)
from ..utils import logging as logging_utils
from .controller import AppController

if TYPE_CHECKING:
    from ..usecases.cancel_runs import CancelRuns

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
        self.win.bind("<Control-Shift-o>", self._on_open_download_folder_hotkey)
        self.win.bind("<Control-Shift-O>", self._on_open_download_folder_hotkey)

        # ---- Shared registries ----
        self.runs = RunsRegistry.instance()

        # ---- ViewModels ----
        self.plate_vm = PlateVM(on_selection_changed=self._on_selection_changed)
        self.experiment_vm = ExperimentVM()
        self.progress_vm = ProgressVM(
            on_update_run_overview=self._apply_run_overview,
            on_update_channel_activity=self._apply_channel_activity,
        )
        self.settings_vm = SettingsVM()
        self._discovery_port = HttpDiscoveryAdapter(default_port=8000)
        self.uc_discover_devices = DiscoverDevices(self._discovery_port)
        self.uc_merge_discovered = MergeDiscoveredIntoRegistry()
        self.live_vm = LiveDataVM()
        self.runs_vm = RunsVM(self.runs)

        # ---- Subviews (constructor callbacks; no .configure(...)) ----
        initial_boxes = tuple(self._configured_boxes())
        self.wellgrid = WellGridView(
            self.win.wellgrid_host,
            boxes=initial_boxes,
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
            boxes=initial_boxes,
            on_cancel_group=self._on_cancel_group,
            on_download_group_results=self._on_download_group_results,
            on_download_box_results=self._on_download_box_results,
            on_open_plot=self._on_open_plotter,
        )
        self.win.mount_run_overview(self.run_overview)

        self.activity = ChannelActivityView(
            self.win.tab_channel_activity, boxes=initial_boxes
        )
        self.win.mount_channel_activity(self.activity)

        self.runs_panel = RunsPanelView(self.win.tabs)
        try:
            # Prefer inserting next to run overview tab for discoverability.
            idx = self.win.tabs.index(self.win.tab_run_overview) + 1
            self.win.tabs.insert(idx, self.runs_panel, text="Runs")
        except Exception:
            self.win.tabs.add(self.runs_panel, text="Runs")

        # ---- REST Adapter & UseCases (lazy init after settings) ----
        self.controller = AppController(self.settings_vm)

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

        # ---- Run flow coordination ----
        self.run_flow = RunFlowPresenter(
            win=self.win,
            controller=self.controller,
            runs=self.runs,
            runs_vm=self.runs_vm,
            progress_vm=self.progress_vm,
            settings_vm=self.settings_vm,
            storage=self._storage,
            plate_vm=self.plate_vm,
            experiment_vm=self.experiment_vm,
            runs_panel=self.runs_panel,
            ensure_adapter=self._ensure_adapter,
            toast_error=self._toast_error,
        )
        self.runs_panel.on_select = self.run_flow.on_runs_select
        self.runs_panel.on_open = self.run_flow.on_runs_open_folder
        self.runs_panel.on_cancel = self.run_flow.on_runs_cancel
        self.runs_panel.on_delete = self.run_flow.on_runs_delete
        self.run_flow.refresh_runs_panel()
        self.run_flow.configure_runs_registry(Path.home() / ".seva" / "runs_registry.json")

        # ---- Initial UI state (demo-ish) ----
        self._seed_demo_state()
        self.win.set_status_message("Ready.")

    def _load_user_settings(self) -> None:
        try:
            payload = self._storage.load_user_settings()
        except Exception as exc:
            self.win.show_toast(f"Could not load settings: {exc}")
            return
        try:
            self.settings_vm.apply_dict(payload)
        except ValueError as exc:
            self.win.show_toast(str(exc))
        self._apply_logging_preferences()
        self._apply_box_configuration()

    def _apply_logging_preferences(self) -> None:
        level = logging_utils.apply_gui_preferences(self.settings_vm.debug_logging)
        self._log.debug(
            "Effective GUI log level: %s", logging_utils.level_name(level)
        )

    def _configured_boxes(self) -> List[str]:
        """Return configured box identifiers, falling back to defaults."""
        base_urls = self.settings_vm.api_base_urls or {}
        boxes = [
            str(box)
            for box, url in base_urls.items()
            if isinstance(url, str) and url.strip()
        ]
        if boxes:
            return sorted(boxes)
        return list(BOX_IDS)

    def _apply_box_configuration(self) -> None:
        """Update views to reflect the currently configured boxes."""
        boxes = self._configured_boxes()
        self.wellgrid.set_boxes(tuple(boxes))
        self.run_overview.set_boxes(boxes)
        self.activity.set_boxes(boxes)

    # ==================================================================
    # Adapter wiring
    # ==================================================================
    def _ensure_adapter(self) -> bool:
        """Ensure controller has adapters and use-cases initialized."""
        if self.controller.ensure_ready():
            return True
        self.win.show_toast("Configure box URLs in Settings first.")
        return False

    # ==================================================================
    # Demo data seeding (light)
    # ==================================================================
    def _seed_demo_state(self) -> None:
        boxes = tuple(self._configured_boxes())
        self.wellgrid.set_boxes(boxes)
        self.wellgrid.set_selection([])
        self.experiment.set_editing_well("-")
        self.experiment.set_electrode_mode("3E")
        # initial empty/idle overview
        self._apply_run_overview({"boxes": {}, "wells": [], "activity": {}})
        self.activity.set_updated_at("")

    # ==================================================================
    # Toolbar / Actions
    # ==================================================================
    def _on_submit(self) -> None:
        """Handle toolbar submit triggered by the user."""
        self.run_flow.start_run()

    def _on_cancel_group(self) -> None:
        self.run_flow.cancel_active_group()

    def _on_end_selection(self) -> None:
        self.run_flow.cancel_selected_runs()

    def _suggest_layout_filename(self) -> str:
        """Return a default layout filename derived from the experiment name."""
        raw_name = (getattr(self.settings_vm, "experiment_name", "") or "").strip()
        sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in raw_name)
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        sanitized = sanitized.strip("_")
        if not sanitized:
            sanitized = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"layout_{sanitized}.json"

    def _on_save_layout(self) -> None:
        try:
            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("Nothing to save: no configured wells.")
                return

            selection = sorted(self.plate_vm.get_selection())
            if selection:
                try:
                    self.experiment_vm.set_selection(set(selection))
                except Exception:
                    pass

            default_name = self._suggest_layout_filename()
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
            saved_path = self.uc_save_layout(  # type: ignore[misc]
                path,
                experiment_vm=self.experiment_vm,
                selection=selection,
            )
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
            data = self.uc_load_layout(  # type: ignore[misc]
                path,
                experiment_vm=self.experiment_vm,
                plate_vm=self.plate_vm,
            )
            configured_wells = self.plate_vm.configured()
            selection_list = list(data.get("selection") or [])
            if not selection_list and configured_wells:
                selection_list = sorted(configured_wells)

            # Mirror electrode mode from VM into view
            try:
                self.experiment.set_electrode_mode(self.experiment_vm.electrode_mode)
            except Exception:
                pass

            # Propagate selection -> view gets updated via _on_selection_changed()
            self.plate_vm.set_selection(selection_list)
            self.wellgrid.set_configured_wells(configured_wells)
            self.wellgrid.set_selection(selection_list)
            # Safety: explizit nochmal synchronisieren (idempotent)
            self._on_selection_changed(set(selection_list))

            self.win.show_toast(f"Loaded {os.path.basename(path)}")
        except Exception as e:
            self.win.show_toast(str(e))

    def _build_discovery_candidates(self) -> List[str]:
        candidates: List[str] = []
        base_urls = self.settings_vm.api_base_urls or {}
        for url in base_urls.values():
            value = (url or "").strip()
            if value:
                candidates.append(value)

        cidr_hints: List[str] = []

        for value in candidates:
            parsed = urlparse(value)
            host = parsed.hostname or ""
            if not host:
                continue
            octets = host.split(".")
            if len(octets) != 4:
                continue
            try:
                if all(0 <= int(part) <= 255 for part in octets):
                    cidr_hints.append(".".join(octets[:3]) + ".0/24")
            except ValueError:
                continue

        ordered: List[str] = []
        seen: Set[str] = set()
        for entry in candidates + cidr_hints:
            normalized = entry.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)

        if not ordered:
            ordered.append("192.168.0.0/24")
        return ordered

    def _on_discover_devices(self, dialog: Optional[SettingsDialog] = None) -> None:
        discover_uc = getattr(self, "uc_discover_devices", None)
        merge_uc = getattr(self, "uc_merge_discovered", None)
        if discover_uc is None or merge_uc is None:
            self.win.show_toast("Discovery not configured.")
            return

        candidates = self._build_discovery_candidates()
        if not candidates:
            self.win.show_toast("No discovery candidates available.")
            return

        try:
            discovered_boxes = discover_uc(candidates=candidates, api_key=None, timeout_s=0.5)
        except Exception as exc:
            self._log.exception("Device discovery failed")
            self.win.show_toast(f"Discovery failed: {exc}")
            return

        if not discovered_boxes:
            self.win.show_toast("Discovery finished. No devices found.")
            return

        current_registry = {
            key: value for key, value in (self.settings_vm.api_base_urls or {}).items() if value
        }
        merged_registry = merge_uc(discovered=discovered_boxes, registry=current_registry)

        normalized_map = {box_id: (self.settings_vm.api_base_urls or {}).get(box_id, "") for box_id in BOX_IDS}
        existing_urls = {url for url in normalized_map.values() if url}
        available_slots = [box_id for box_id, url in normalized_map.items() if not url]

        new_urls: List[str] = []
        seen_urls: Set[str] = set()
        for url in merged_registry.values():
            trimmed = (url or "").strip()
            if trimmed and trimmed not in seen_urls:
                seen_urls.add(trimmed)
                new_urls.append(trimmed)

        newly_assigned: Dict[str, str] = {}
        skipped_urls: List[str] = []
        for url in new_urls:
            if url in existing_urls:
                continue
            if not available_slots:
                skipped_urls.append(url)
                continue
            box_id = available_slots.pop(0)
            normalized_map[box_id] = url
            newly_assigned[box_id] = url
            existing_urls.add(url)

        persistence_error: Optional[Exception] = None
        normalized_payload = {box_id: normalized_map.get(box_id, "") for box_id in BOX_IDS}
        if newly_assigned:
            try:
                self.settings_vm.api_base_urls = normalized_payload
            except ValueError as exc:
                self.win.show_toast(f"Could not apply discovered devices: {exc}")
                return
            try:
                self._storage.save_user_settings(self.settings_vm.to_dict())
            except Exception as exc:
                persistence_error = exc
                self._log.exception("Failed to persist discovered devices")
            if dialog and dialog.winfo_exists():
                dialog.set_api_base_urls(normalized_payload)
                dialog.set_save_enabled(self.settings_vm.is_valid())

        summary_seen: Set[tuple[str, Optional[str], Optional[str]]] = set()
        summary_parts: List[str] = []
        for box in discovered_boxes:
            base_url = (getattr(box, "base_url", "") or "").strip()
            if not base_url:
                continue
            key = (base_url, getattr(box, "box_id", None), getattr(box, "build", None))
            if key in summary_seen:
                continue
            summary_seen.add(key)
            label = getattr(box, "box_id", None) or getattr(box, "build", None) or "unknown"
            summary_parts.append(f"{base_url} ({label})")

        found_summary = ", ".join(summary_parts) if summary_parts else "none"

        message_bits: List[str] = [f"Found: {found_summary}"]
        if newly_assigned:
            assigned_summary = ", ".join(f"{box_id}={url}" for box_id, url in newly_assigned.items())
            message_bits.append(f"Assigned {assigned_summary}")
        if skipped_urls:
            skipped_summary = ", ".join(skipped_urls)
            message_bits.append(f"No free slots for {skipped_summary}")
        if persistence_error:
            message_bits.append(f"Persistence failed ({persistence_error})")

        self.win.show_toast("Discovery finished. " + "; ".join(message_bits))
        # --- NEW: Pop-up table with discovered devices ---
        rows = []
        for box in discovered_boxes:
            rows.append({
                "base_url": (getattr(box, "base_url", "") or "").strip(),
                "box_id": getattr(box, "box_id", None),
                "devices": getattr(box, "devices", None),
                "api_version": getattr(box, "api_version", None),
                "build": getattr(box, "build", None),
            })
        DiscoveryResultsDialog(self.win, rows)

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

            adapter = self.controller.device_adapter
            if adapter is None:
                saved_url = (self.settings_vm.api_base_urls or {}).get(box_id, "").strip()
                if saved_url:
                    if self._ensure_adapter():
                        adapter = self.controller.device_adapter

            uc = self.controller.build_test_connection(
                box_id=box_id,
                base_url=base_url,
                api_key=api_key,
                request_timeout=request_timeout,
            )

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
            dlg.set_results_dir(new_dir)

        def handle_browse_firmware() -> None:
            if not dlg:
                return
            current = dlg.firmware_path_var.get().strip()
            initial_dir = ""
            if current:
                expanded = os.path.expanduser(current)
                if os.path.isdir(expanded):
                    initial_dir = expanded
                elif os.path.isfile(expanded):
                    initial_dir = os.path.dirname(expanded)
            try:
                selected = filedialog.askopenfilename(
                    parent=dlg,
                    initialdir=initial_dir or None,
                    title="Select Firmware Image",
                    filetypes=[("Firmware Image", "*.bin"), ("All Files", "*.*")],
                )
            except Exception as exc:
                self.win.show_toast(f"Could not open file picker: {exc}")
                return
            if not selected:
                return
            dlg.set_firmware_path(os.path.normpath(selected))

        def handle_flash_firmware() -> None:
            if not dlg:
                return
            firmware_path = dlg.firmware_path_var.get().strip()
            if not firmware_path:
                self.win.show_toast("Select a firmware .bin file first.")
                return
            if not self._ensure_adapter():
                return
            uc = self.controller.uc_flash_firmware
            if uc is None:
                self.win.show_toast("Firmware flashing is not available.")
                return
            box_ids = sorted(
                box_id
                for box_id, url in (self.settings_vm.api_base_urls or {}).items()
                if isinstance(url, str) and url.strip()
            )
            try:
                result = uc(box_ids=box_ids, firmware_path=firmware_path)
            except Exception as exc:
                self._toast_error(exc, context="Flash firmware")
                return

            if result.failures:
                failed_boxes = ", ".join(sorted(result.failures.keys()))
                self.win.show_toast(f"Firmware flash failed on {failed_boxes}.")
                details = "\n".join(
                    f"{box_id}: {err}" for box_id, err in result.failures.items()
                )
                messagebox.showerror("Firmware Flash Failed", details, parent=dlg)
                return

            flashed_boxes = ", ".join(sorted(result.successes.keys()))
            if flashed_boxes:
                self.win.show_toast(f"Firmware flashed on {flashed_boxes}.")
            else:
                self.win.show_toast("Firmware flash completed.")

        def handle_open_nas_setup() -> None:
            NASSetupGUI(self.win)

        dlg = SettingsDialog(
            self.win,
            on_test_connection=handle_test_connection,
            on_test_relay=handle_test_relay,
            on_browse_results_dir=handle_browse_results_dir,
            on_browse_firmware=handle_browse_firmware,
            on_discover_devices=lambda: self._on_discover_devices(dlg),
            on_open_nas_setup=handle_open_nas_setup,
            on_save=self._on_settings_saved,
            on_flash_firmware=handle_flash_firmware,
            on_close=lambda: None,
        )
        # Populate dialog from VM
        dlg.set_api_base_urls(self.settings_vm.api_base_urls)
        dlg.set_api_keys(self.settings_vm.api_keys)
        dlg.set_timeouts(
            self.settings_vm.request_timeout_s, self.settings_vm.download_timeout_s
        )
        dlg.set_poll_interval(self.settings_vm.poll_interval_ms)
        dlg.set_poll_backoff_max(self.settings_vm.poll_backoff_max_ms)
        dlg.set_results_dir(self.settings_vm.results_dir)
        dlg.set_experiment_name(self.settings_vm.experiment_name)
        dlg.set_subdir(self.settings_vm.subdir)
        dlg.set_auto_download(self.settings_vm.auto_download_on_complete)
        dlg.set_use_streaming(self.settings_vm.use_streaming)
        dlg.set_debug_logging(self.settings_vm.debug_logging)
        dlg.set_relay_config(self.settings_vm.relay_ip, self.settings_vm.relay_port)
        dlg.set_firmware_path(self.settings_vm.firmware_path)
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
        self.run_flow.stop_all_polling()
        self.controller.reset()
        self._apply_box_configuration()
        self.win.show_toast("Settings saved.")

    def _on_open_plotter(self) -> None:
        DataProcessingGUI(self.win)

    def _on_download_group_results(self) -> None:
        group_id = self.run_flow.active_group_id
        if not group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        storage_meta = self.run_flow.group_storage_meta_for(group_id)
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
            out_dir = self.controller.uc_download(
                group_id,
                results_dir,
                storage_meta,
                cleanup="archive",
            )  # type: ignore[misc]
            self._log.info(
                "Downloaded group %s to %s", group_id, out_dir
            )
            resolved_dir = os.path.abspath(out_dir)
            self.run_flow.record_download_dir(resolved_dir)
            self.win.show_toast(self.run_flow.build_download_toast(group_id, resolved_dir))
        except Exception as e:
            self._toast_error(e)

    def _on_download_box_results(self, box_id: str) -> None:
        # Group ZIPs are per group; per-box filtering could be added in adapter if needed
        self._on_download_group_results()

    def _can_open_results_folder(self) -> bool:
        if sys.platform.startswith("win"):
            return hasattr(os, "startfile")
        if sys.platform == "darwin":
            return True
        return shutil.which("xdg-open") is not None

    def _on_open_download_folder_hotkey(self, event=None):
        if not self.run_flow.last_download_dir:
            self.win.show_toast("Nothing downloaded yet.")
            return "break"
        if not self._can_open_results_folder():
            self.win.show_toast("Open folder not supported on this platform.")
            return "break"
        self._open_results_folder(self.run_flow.last_download_dir)
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
        """Always clear first, then (if single) set snapshot + label."""
        # Clear the view first to avoid stale values
        self.experiment.clear_fields()

        if len(sel) == 1:
            wid = next(iter(sel))
            # Label aktualisieren
            try:
                self.experiment.set_editing_well(wid)
            except Exception:
                pass
            # Flatten grouped snapshot and set
            params = self.experiment_vm.get_params_for(wid)
            if params:
                self.experiment.set_fields(params)
        else:
            self.experiment.set_editing_well("–")

    def _on_apply_params(self) -> None:
        selection = self.plate_vm.get_selection()
        if not selection:
            self.win.show_toast("No wells selected.")
            return
        # Save grouped per well (only active modes)
        for wid in selection:
            self.experiment_vm.save_params_for(wid, self.experiment_vm.fields)
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
        label = self.progress_vm.updated_at_label or time.strftime("%H:%M:%S")
        self.activity.set_updated_at(label)

    def _open_plot_for_well(self, well_id: str) -> None:
        self.win.show_toast(f"Open PNG for {well_id}")

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

    


def main() -> None:
    app = App()
    app.win.mainloop()


if __name__ == "__main__":
    main()
