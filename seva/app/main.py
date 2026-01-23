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
from dataclasses import dataclass
from typing import Any, Dict, Set, Optional, List, TYPE_CHECKING

# ---- Views (UI-only) ----
from .views.main_window import MainWindowView
from .views.well_grid_view import WellGridView
from .views.experiment_panel_view import ExperimentPanelView
from .views.run_overview_view import RunOverviewView
from .views.channel_activity_view import ChannelActivityView
from .views.settings_dialog import SettingsDialog
from .views.data_plotter import DataPlotter
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
from ..usecases.start_experiment_batch import StartBatchResult
from ..usecases.run_flow_coordinator import (
    FlowHooks,
    FlowTick,
    GroupContext,
    RunFlowCoordinator,
)
from ..adapters.storage_local import StorageLocal
from ..adapters.discovery_http import HttpDiscoveryAdapter
from ..adapters.relay_mock import RelayMock
from ..usecases.save_plate_layout import SavePlateLayout
from ..usecases.load_plate_layout import LoadPlateLayout
from ..domain.entities import ExperimentPlan
from ..domain.plan_builder import build_meta
from ..domain.util import well_id_to_box
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


@dataclass
class FlowSession:
    """Runtime wiring for a tracked run group managed by the app."""

    coordinator: RunFlowCoordinator
    context: GroupContext
    after_id: Optional[str] = None


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

        # ---- Shared registries ----
        self.runs = RunsRegistry.instance()
        self._sessions: Dict[str, FlowSession] = {}
        self._active_group_id: Optional[str] = None

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

        self.runs_panel.on_select = self._on_runs_select
        self.runs_panel.on_open = self._on_runs_open_folder
        self.runs_panel.on_cancel = self._on_runs_cancel
        self.runs_panel.on_delete = self._on_runs_delete
        self._refresh_runs_panel()

        # ---- REST Adapter & UseCases (lazy init after settings) ----
        self.controller = AppController(self.settings_vm)

        # ---- Download metadata per group ----
        self._group_storage_meta: Dict[str, Dict[str, str]] = {}
        self._last_plan_inputs: Optional[Dict[str, Any]] = None

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
        self._configure_runs_registry()

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

    def _configure_runs_registry(self) -> None:
        """Configure the runs registry and re-attach persisted groups."""
        store_path = Path.home() / ".seva" / "runs_registry.json"
        self.runs.configure(
            store_path=store_path,
            hooks_factory=self._build_flow_hooks_for_group,
            coordinator_factory=self._coordinator_factory_for_group,
        )
        try:
            self.runs.load()
        except Exception as exc:
            self._log.warning("Failed to load runs registry: %s", exc)
            return

        for group_id in self.runs.active_groups():
            try:
                context = self.runs.start_tracking(group_id)
            except Exception as exc:
                self._log.error("Failed to re-attach group %s: %s", group_id, exc)
                continue
            coordinator = self.runs.coordinator_for(group_id)
            if not coordinator or not context:
                continue
            self._register_session(group_id, coordinator, context)
            self._schedule_poll(group_id, 0)
        self._refresh_runs_panel()

    def _build_flow_hooks_for_group(self, group_id: str) -> FlowHooks:
        """Create FlowHooks bound to a specific run group."""
        return FlowHooks(
            on_started=lambda ctx: self._on_group_started(group_id, ctx),
            on_snapshot=lambda snapshot: self._on_group_snapshot(group_id, snapshot),
            on_completed=lambda path: self._on_group_completed(group_id, path),
            on_error=lambda message: self._on_group_error(group_id, message),
        )

    def _coordinator_factory_for_group(
        self,
        group_id: str,
        plan_meta: Dict[str, Any],
        storage_meta: Dict[str, str],
        hooks: FlowHooks,
    ) -> RunFlowCoordinator:
        """Factory callback passed to RunsRegistry for re-attachments."""
        if not self._ensure_adapter():
            raise RuntimeError("Adapters not configured for coordinator factory.")
        coordinator = RunFlowCoordinator(
            job_port=self.controller.job_adapter,
            storage_port=self._storage,
            uc_start=self.controller.uc_start,
            uc_poll=self.controller.uc_poll,
            uc_download=self.controller.uc_download,
            settings=self.settings_vm,
            hooks=hooks,
        )
        return coordinator

    def _register_session(
        self, group_id: str, coordinator: RunFlowCoordinator, context: GroupContext
    ) -> None:
        """Register a runtime session both locally and in the registry."""
        self.runs.register_runtime(group_id, coordinator, context)
        existing = self._sessions.get(group_id)
        if existing and existing.after_id:
            try:
                self.win.after_cancel(existing.after_id)
            except Exception:
                pass
        self._sessions[group_id] = FlowSession(coordinator=coordinator, context=context)
        self._group_storage_meta.setdefault(group_id, dict(context.storage_meta))
        if not self._active_group_id:
            self._active_group_id = group_id
            self.win.set_run_group_id(group_id)
            self.runs_vm.set_active_group(group_id)
            self.progress_vm.set_active_group(group_id, self.runs)
        self._refresh_runs_panel()

    # ==================================================================
    # Runs panel helpers
    # ==================================================================
    def _refresh_runs_panel(self) -> None:
        if not hasattr(self, "runs_panel"):
            return
        rows = self.runs_vm.rows()
        self.runs_panel.set_rows(rows)
        active = self.runs_vm.active_group_id or self._active_group_id
        current_vm = getattr(self.progress_vm, "active_group_id", None)
        if active and active != current_vm:
            self.runs_panel.select_group(active)

    def _open_path(self, path: str) -> None:
        if not path:
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.check_call(["open", path])
            else:
                subprocess.check_call(["xdg-open", path])
        except Exception:
            messagebox.showwarning("Open Folder", f"Kann Ordner nicht öffnen:\n{path}")

    def _on_runs_select(self, group_id: str) -> None:
        # Wenn bereits aktiv, nichts neu rendern.
        if self.progress_vm.active_group_id == group_id:
            self.runs_vm.set_active_group(group_id)
            self._active_group_id = group_id
            self.win.set_run_group_id(group_id)
            return

        self.runs_vm.set_active_group(group_id)
        self.progress_vm.set_active_group(group_id, self.runs)
        self._active_group_id = group_id
        self.win.set_run_group_id(group_id)

    def _on_runs_open_folder(self, group_id: str) -> None:
        entry = self.runs.get(group_id)
        if not entry:
            return
        path = (entry.download.path or "").strip()
        if not path:
            messagebox.showinfo("Open Folder", "Noch kein Download-Verzeichnis vorhanden.")
            return
        self._open_path(path)

    def _on_runs_cancel(self, group_id: str) -> None:
        if not self._ensure_adapter() or not self.controller.uc_cancel:
            messagebox.showinfo("Cancel Group", "Cancel use case nicht verfügbar.")
            return

        entry = self.runs.get(group_id)
        if not entry:
            messagebox.showinfo("Cancel Group", "Eintrag nicht gefunden.")
            return
        if entry.status not in {"running", "pending"}:
            messagebox.showinfo("Cancel Group", "Run ist nicht mehr aktiv.")
            return
        if not messagebox.askyesno("Cancel Group", f"Gruppe {group_id} wirklich abbrechen?"):
            return

        try:
            self.controller.uc_cancel(group_id)  # type: ignore[misc]
            self._stop_polling(group_id)
            self.runs.mark_cancelled(group_id)
            self._refresh_runs_panel()
        except Exception as exc:
            messagebox.showerror("Cancel Group", f"Abbrechen fehlgeschlagen:\n{exc}")

    def _on_runs_delete(self, group_id: str) -> None:
        entry = self.runs.get(group_id)
        if not entry:
            return

        if entry.status in {"running", "pending"}:
            if not messagebox.askyesno(
                "Cancel Group", f"Gruppe {group_id} läuft noch. Jetzt abbrechen?"
            ):
                return
            self._on_runs_cancel(group_id)
            return

        if not messagebox.askyesno("Remove", f"Eintrag {group_id} aus der Liste entfernen?"):
            return

        self._stop_polling(group_id)
        self.runs.remove(group_id)
        if self.runs_vm.active_group_id == group_id:
            self.runs_vm.set_active_group(None)
            self.progress_vm.set_active_group(None, self.runs)
        if self._active_group_id == group_id:
            self._active_group_id = next(iter(self._sessions), None)
            self.win.set_run_group_id(self._active_group_id or "")
        self._refresh_runs_panel()

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
        # Submit: kick off coordinator flow.
        try:
            if not self._ensure_adapter():
                return

            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("No configured wells to start.")
                return

            selection = self.plate_vm.get_selection()
            self.experiment_vm.set_selection(selection)
            plan = self._build_domain_plan()
            boxes = sorted(
                {
                    box
                    for wid in configured
                    if isinstance(wid, str)
                    for box in [well_id_to_box(wid)]
                    if box is not None
                }
            )
            summary = {
                "wells": len(configured),
                "boxes": boxes or ["-"],
                "stream": bool(self.settings_vm.use_streaming),
            }
            self._log.info("Submitting start request: %s", summary)
            self._log.debug("Start selection=%s", sorted(configured))

            start_hooks = FlowHooks()
            coordinator = RunFlowCoordinator(
                job_port=self.controller.job_adapter,
                storage_port=self._storage,
                uc_start=self.controller.uc_start,
                uc_poll=self.controller.uc_poll,
                uc_download=self.controller.uc_download,
                settings=self.settings_vm,
                hooks=start_hooks,
            )

            try:
                ctx = coordinator.start(plan)
            except UseCaseError as e:
                if getattr(e, "code", "") == "SLOT_BUSY":
                    meta = getattr(e, "meta", None) or {}
                    busy = []
                    if isinstance(meta, dict) and isinstance(meta.get("busy_wells"), list):
                        busy = [str(w) for w in meta.get("busy_wells")]
                    msg = e.message or "Slots busy."
                    try:
                        # If MainWindowView supports a warn kind, otherwise plain toast
                        self.win.show_toast(f"Start abgelehnt: {msg}")
                    except Exception:
                        self.win.show_toast(f"Start abgelehnt: {msg}")
                    # Optional: flash wells if supported by PlateVM view
                    if busy and hasattr(self.plate_vm, "flash_wells"):
                        try:
                            self.plate_vm.flash_wells(busy)
                        except Exception:
                            pass
                    coordinator.stop_polling()
                    return
                raise
            start_result = coordinator.last_start_result()
            if not isinstance(start_result, StartBatchResult):
                raise RuntimeError("Coordinator returned an unexpected start result.")

            if not start_result.run_group_id:
                coordinator.stop_polling()
                return

            group_id = str(start_result.run_group_id)
            subruns = start_result.per_box_runs
            meta = plan.meta
            storage_inputs = self._last_plan_inputs or {}
            normalized_storage = {
                "experiment": meta.experiment,
                "subdir": meta.subdir or "",
                "client_datetime": self._format_client_datetime_for_storage(meta.client_dt.value),
                "results_dir": str(
                    storage_inputs.get("results_dir") or self.settings_vm.results_dir or ""
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

            ctx.storage_meta.update(normalized_storage)
            plan_meta_payload = {
                "experiment": meta.experiment,
                "subdir": meta.subdir or "",
                "client_datetime": meta.client_dt.value.isoformat(),
                "group_id": group_id,
            }
            self.runs.add(
                group_id=group_id,
                name=meta.experiment,
                boxes=sorted(subruns.keys()),
                runs_by_box=subruns,
                plan_meta=plan_meta_payload,
                storage_meta=normalized_storage,
            )
            self._refresh_runs_panel()

            tracking_hooks = self._build_flow_hooks_for_group(group_id)
            coordinator.hooks = tracking_hooks
            self._register_session(group_id, coordinator, ctx)
            self.runs.start_tracking(group_id)

            self._active_group_id = group_id
            self.win.set_run_group_id(group_id)

            started_boxes = ", ".join(sorted(subruns.keys()))
            if started_boxes:
                self.win.show_toast(f"Started group {group_id} on {started_boxes}")
            else:
                self.win.show_toast(f"Started group {group_id}.")
            self._schedule_poll(group_id, 0)
        except Exception as e:
            self._stop_polling()
            self._toast_error(e)

    def _on_cancel_group(self) -> None:
        if not self._active_group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        try:
            current = self._active_group_id
            self._log.info("Cancel requested for group %s", current)
            self.controller.uc_cancel(current)  # type: ignore[misc]
            self._stop_polling(current)
            self.runs.mark_cancelled(current)
            self.win.show_toast(f"Cancel requested for group {current}.")
            self._refresh_runs_panel()
            self.progress_vm.set_active_group(current, self.runs)
        except Exception as e:
            self._toast_error(e)

    def _on_end_selection(self) -> None:
        selection = sorted(self.plate_vm.get_selection())
        if not selection:
            self.win.show_toast("Select at least one well.")
            return
        if not self._ensure_adapter():
            return
        cancel_runs = self.controller.uc_cancel_runs
        if cancel_runs is None:
            self.win.show_toast("Cancel selected runs not available.")
            return

        payload = self.progress_vm.map_selection_to_runs(selection)
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

            # Elektrode-Mode aus VM in View spiegeln
            try:
                self.experiment.set_electrode_mode(self.experiment_vm.electrode_mode)
            except Exception:
                pass

            # Auswahl propagieren → View wird über _on_selection_changed() aktualisiert
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

        dlg = SettingsDialog(
            self.win,
            on_test_connection=handle_test_connection,
            on_test_relay=handle_test_relay,
            on_browse_results_dir=handle_browse_results_dir,
            on_discover_devices=lambda: self._on_discover_devices(dlg),
            on_save=self._on_settings_saved,
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
        self.controller.reset()
        self._apply_box_configuration()
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
        selection_summary = ", ".join(sorted(self.plate_vm.get_selection())) or "-"
        dp.set_run_info(self._active_group_id or "-", selection_summary)

    def _on_download_group_results(self) -> None:
        group_id = self._active_group_id
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
        if not meta and group_id:
            entry = self.runs.get(group_id)
            if entry:
                meta = entry.storage_meta
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
        """Always clear first, then (if single) set snapshot + label."""
        # Erst View leeren, um „hängende“ Werte zu vermeiden
        self.experiment.clear_fields()

        if len(sel) == 1:
            wid = next(iter(sel))
            # Label aktualisieren
            try:
                self.experiment.set_editing_well(wid)
            except Exception:
                pass
            # Gruppierten Snapshot flatten und setzen
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
        # Pro Well gruppiert speichern (nur aktivierte Modi)
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
    # Polling helpers
    # ==================================================================
    def _stop_polling(self, group_id: Optional[str] = None) -> None:
        """Cancel scheduled polls and stop coordinators."""
        if group_id is None:
            for gid in list(self._sessions.keys()):
                self._stop_polling(gid)
            return

        session = self._sessions.get(group_id)
        if not session:
            return
        self._cancel_poll_timer(group_id)
        try:
            session.coordinator.stop_polling()
        except Exception:
            pass
        self.runs.unregister_runtime(group_id)
        self._sessions.pop(group_id, None)
        if self._active_group_id == group_id:
            self._active_group_id = next(iter(self._sessions), None)
            self.win.set_run_group_id(self._active_group_id or "")

    def _cancel_poll_timer(self, group_id: Optional[str]) -> None:
        """Cancel scheduled Tk timer(s) for polling."""
        if group_id is None:
            for gid in list(self._sessions.keys()):
                self._cancel_poll_timer(gid)
            return
        session = self._sessions.get(group_id)
        if session and session.after_id is not None:
            try:
                self.win.after_cancel(session.after_id)
            except Exception:
                pass
            session.after_id = None

    def _schedule_poll(self, group_id: str, delay_ms: int) -> None:
        """Schedule the next poll tick for a given group."""
        session = self._sessions.get(group_id)
        if not session:
            return
        delay = max(1, int(delay_ms))
        self._cancel_poll_timer(group_id)
        session.after_id = self.win.after(
            delay, lambda gid=group_id: self._on_poll_tick(gid)
        )

    def _on_poll_tick(self, group_id: str) -> None:
        """Cooperative poll tick executed on the Tkinter thread."""
        session = self._sessions.get(group_id)
        if not session:
            return
        if not self._ensure_adapter():
            return

        coordinator = session.coordinator
        context = session.context

        tick: FlowTick = coordinator.poll_once(context)
        if tick.event == "tick":
            delay = tick.next_delay_ms
            if delay is None:
                base = getattr(self.settings_vm, "poll_interval_ms", 1000) or 1000
                try:
                    delay = max(200, int(base))
                except (TypeError, ValueError):
                    delay = 1000
            self._schedule_poll(group_id, int(delay))
            return

        # Completed/Error: no further scheduling; rely on hooks for UI feedback.
        self._cancel_poll_timer(group_id)
        if tick.event == "completed":
            coordinator.stop_polling()
            auto_download_enabled = getattr(
                self.settings_vm, "auto_download_on_complete", True
            )
            download_path: Optional[Path] = None
            if tick.snapshot:
                try:
                    download_path = coordinator.on_completed(context, tick.snapshot)
                except Exception as exc:
                    self._toast_error(exc, context="Download failed")
                    self._finalize_session(group_id)
                    return
            if not auto_download_enabled:
                self._on_group_completed(group_id, None)
            self._finalize_session(group_id)
            return

        if tick.event == "error":
            coordinator.stop_polling()
            self._finalize_session(group_id)

    def _finalize_session(self, group_id: str) -> None:
        """Clean up local bookkeeping once a run no longer needs polling."""
        session = self._sessions.pop(group_id, None)
        if session and session.after_id is not None:
            try:
                self.win.after_cancel(session.after_id)
            except Exception:
                pass
        self.runs.unregister_runtime(group_id)
        if self._active_group_id == group_id:
            self._active_group_id = next(iter(self._sessions), None)
            self.win.set_run_group_id(self._active_group_id or "")
        self._refresh_runs_panel()

    def _on_group_started(self, group_id: str, ctx: GroupContext) -> None:
        """Hook fired when a coordinator acknowledges start for a group."""
        self._log.debug("Coordinator acknowledged start for group %s", ctx.group)

    def _on_group_snapshot(self, group_id: str, snapshot) -> None:
        """Hook fired on every polling snapshot for a group."""
        self.runs.update_snapshot(group_id, snapshot)
        if snapshot and group_id == self._active_group_id:
            self.progress_vm.apply_snapshot(snapshot)
        self._refresh_runs_panel()

    def _on_group_completed(self, group_id: str, path: Optional[Path]) -> None:
        """Hook fired when the flow reports completion for a group."""
        download_path = os.path.abspath(str(path)) if path else None
        self.runs.mark_done(group_id, download_path)
        if download_path:
            self._last_download_dir = download_path
            self.win.show_toast(self._build_download_toast(group_id, download_path))
        else:
            self.win.show_toast("All runs completed.")
        self._refresh_runs_panel()
        if getattr(self.progress_vm, "active_group_id", None) == group_id:
            self.progress_vm.set_active_group(group_id, self.runs)

    def _on_group_error(self, group_id: str, message: str) -> None:
        """Hook fired when the flow reports a polling error for a group."""
        text = message.strip() if isinstance(message, str) else ""
        if text:
            self._log.error("Polling error for %s: %s", group_id, text)
        else:
            self._log.error("Polling error for %s: <empty message>", group_id)
        self.runs.mark_error(group_id, text or None)
        self.win.show_toast(text or "Polling failed.")
        self._refresh_runs_panel()

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

    # ==================================================================
    # Plan building
    # ==================================================================

    def _build_domain_plan(self) -> ExperimentPlan:
        """Build a domain ExperimentPlan from the current view-model state."""
        configured = self.plate_vm.configured()
        if not configured:
            raise RuntimeError("No configured wells to start.")
        
        well_plan_list = self.experiment_vm.build_well_plan_map(configured)
        if not well_plan_list:
            raise RuntimeError("No saved parameters found for configured wells.")

        inputs = self._collect_plan_inputs()
        meta = build_meta(
            experiment=inputs["experiment"],
            subdir=inputs["subdir"],
            client_dt_local=inputs["client_dt"],
        )
        # Persist plan inputs so downstream UI storage metadata can reuse them.
        self._last_plan_inputs = inputs

        return ExperimentPlan(
            meta=meta,
            wells=well_plan_list
        )

    def _collect_plan_inputs(self) -> Dict[str, Any]:
        """Gather experiment metadata and filesystem settings for plan construction."""
        experiment_name = (self.settings_vm.experiment_name or "").strip()
        if not experiment_name:
            raise RuntimeError("Experiment name must be set in Settings.")

        subdir_raw = (self.settings_vm.subdir or "").strip()
        subdir = subdir_raw or None

        override_dt = ""
        if hasattr(self.experiment_vm, "fields"):
            override_dt = str(self.experiment_vm.fields.get("storage.client_datetime") or "")
        client_dt = self._parse_client_datetime_override(override_dt)

        results_dir = str(self.settings_vm.results_dir or "").strip() or "."

        return {
            "experiment": experiment_name,
            "subdir": subdir,
            "client_dt": client_dt,
            "results_dir": results_dir,
        }

    def _parse_client_datetime_override(self, value: str) -> datetime:
        """Interpret stored client datetime overrides, falling back to the current time."""
        text = str(value or "").strip()
        if not text:
            return datetime.now().astimezone().replace(microsecond=0)

        normalized = text.replace(" ", "T")
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        if "T" in normalized:
            date_part, time_part = normalized.split("T", 1)
            if ":" not in time_part:
                time_part = time_part.replace("-", ":")
            normalized = f"{date_part}T{time_part}"

        parsed = None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            pass

        if parsed is None:
            for fmt in ("%Y-%m-%d_%H-%M-%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H-%M-%S"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue

        if parsed is None:
            return datetime.now().astimezone().replace(microsecond=0)

        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            local_zone = datetime.now().astimezone().tzinfo
            parsed = parsed.replace(tzinfo=local_zone)

        return parsed.astimezone().replace(microsecond=0)

    @staticmethod
    def _format_client_datetime_for_storage(dt: datetime) -> str:
        """Return a filesystem-safe representation of the client datetime."""
        return dt.astimezone().strftime("%Y-%m-%d_%H-%M-%S")


def main() -> None:
    app = App()
    app.win.mainloop()


if __name__ == "__main__":
    main()
