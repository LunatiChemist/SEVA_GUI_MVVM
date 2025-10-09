# seva/app/main.py
from __future__ import annotations
from typing import Dict, Set, Optional, Iterable, Tuple

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
from ..usecases.start_experiment_batch import StartExperimentBatch
from ..usecases.poll_group_status import PollGroupStatus
from ..usecases.download_group_results import DownloadGroupResults
from ..usecases.cancel_group import CancelGroup
from ..adapters.job_rest import JobRestAdapter
from ..adapters.storage_local import StorageLocal
from ..usecases.save_plate_layout import SavePlateLayout
from ..usecases.load_plate_layout import LoadPlateLayout


class App:
    """Bootstrap: wire Views <-> ViewModels, REST adapter, and simple polling."""

    def __init__(self) -> None:
        # Main window with toolbar callback wiring
        self.win = MainWindowView(
            on_submit=self._on_submit,
            on_cancel_group=self._on_cancel_group,
            on_cancel_selection=self._on_cancel_selection,
            on_save_layout=self._on_save_layout,
            on_load_layout=self._on_load_layout,
            on_open_settings=self._on_open_settings,
            on_open_data_plotter=self._on_open_plotter,
        )

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
            on_reset_selected=lambda: None,
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
            on_copy_cv=None,
            on_paste_cv=None,
            on_copy_dcac=None,
            on_paste_dcac=None,
            on_copy_cdl=None,
            on_paste_cdl=None,
            on_electrode_mode_changed=self._on_electrode_mode_changed,  # relay-only, not part of REST
        )
        self.win.mount_experiment_panel(self.experiment)

        self.run_overview = RunOverviewView(
            self.win.tab_run_overview,
            boxes=("A", "B", "C", "D"),
            on_cancel_group=self._on_cancel_group,
            on_cancel_selection=self._on_cancel_selection,
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
        self.uc_start: Optional[StartExperimentBatch] = None
        self.uc_poll: Optional[PollGroupStatus] = None
        self.uc_download: Optional[DownloadGroupResults] = None
        self.uc_cancel: Optional[CancelGroup] = None

        # ---- LocalStorage Adapter ----
        self._storage = StorageLocal(root_dir=self.settings_vm.results_dir or ".")
        self.uc_save_layout = SavePlateLayout(self._storage)
        self.uc_load_layout = LoadPlateLayout(self._storage)

        # ---- Polling state ----
        self._current_group_id: Optional[str] = None
        self._polling_active: bool = False

        # ---- Initial UI state (demo-ish) ----
        self._seed_demo_state()
        self.win.set_status_message("Ready.")

    # ==================================================================
    # Adapter wiring
    # ==================================================================
    def _ensure_adapter(self) -> bool:
        """Build the REST adapter and use cases from SettingsVM if not yet present."""
        if self._job_adapter:
            return True

        base_urls = {k: v for k, v in (self.settings_vm.box_urls or {}).items() if v}
        if not base_urls:
            self.win.show_toast("Configure box URLs in Settings first.")
            return False

        api_keys = {k: v for k, v in (self.settings_vm.api_keys or {}).items() if v}
        self._job_adapter = JobRestAdapter(
            base_urls=base_urls,
            api_keys=api_keys,
            request_timeout_s=self.settings_vm.request_timeout_s,
            download_timeout_s=self.settings_vm.download_timeout_s,
            retries=2,
        )
        self.uc_start = StartExperimentBatch(self._job_adapter)
        self.uc_poll = PollGroupStatus(self._job_adapter)
        self.uc_download = DownloadGroupResults(self._job_adapter)
        self.uc_cancel = CancelGroup(self._job_adapter)
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
        try:
            if not self._ensure_adapter():
                return
            # collect selection & plan
            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("No configured wells to start.")
                return

            # Falls du die Selektion noch für die UI-Toast brauchst:
            selection = self.plate_vm.get_selection()
            self.experiment_vm.set_selection(selection)
            plan = self._build_plan_from_vm(selection)

            # Start via UseCase
            group_id, subruns = self.uc_start(plan)  # type: ignore[misc]
            self._current_group_id = group_id
            self.win.set_run_group_id(group_id)
            self.win.show_toast(
                f"Started group {group_id} on {', '.join(sorted(subruns.keys()))}"
            )

            # Mark configured in UI (keep the Demo flow)
            self.wellgrid.add_configured_wells(selection)

            # Start polling loop
            self._start_polling()
        except Exception as e: 
            # Stop polling and clear group on any start failure
            self._stop_polling()
            self._current_group_id = None 
            self.win.show_toast(str(e))

    def _on_cancel_group(self) -> None:
        if not self._current_group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        try:
            self.uc_cancel(self._current_group_id)  # prints notice in adapter
            self._stop_polling()
            self._current_group_id = None
            self.win.set_run_group_id("")        # optional UI cleanup
            self.win.show_toast("Cancel requested (API not implemented).")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_cancel_selection(self) -> None:
        self.wellgrid.set_selection([])

    def _on_save_layout(self) -> None:
        try:
            configured = self.plate_vm.configured()
            if not configured:
                self.win.show_toast("Nothing to save: no configured wells.")
                return
            well_map = self.experiment_vm.build_well_params_map(configured)
            # Use a simple default name; later ask the user
            name = "layout_latest"
            self.uc_save_layout(name, configured, well_map)  # type: ignore[misc]
            self.win.show_toast(f"Layout saved as {name}.csv")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_load_layout(self) -> None:
        try:
            name = "layout_latest"  # later: open file picker / presets
            data = self.uc_load_layout(name)  # type: ignore[misc]
            wmap: Dict[str, Dict[str, str]] = data.get("well_params_map", {})
            wells = set(data.get("selection", []))
            # push into VM
            for wid, snap in wmap.items():
                self.experiment_vm.save_params_for(wid, snap)
            # reflect in UI/VM
            self.plate_vm.clear_all_configured()
            self.plate_vm.mark_configured(wells)
            self.wellgrid.set_configured_wells(wells)
            self.win.show_toast(f"Layout {name}.csv loaded ({len(wells)} wells).")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(
            self.win,
            on_test_connection=lambda b: self.win.show_toast(f"Test box {b} (demo)"),
            on_test_relay=lambda: self.win.show_toast("Test relay (demo)"),
            on_browse_results_dir=lambda: self.win.show_toast(
                "Browse results dir (demo)"
            ),
            on_save=self._on_settings_saved,
            on_cancel=lambda: None,
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
        dlg.set_use_streaming(self.settings_vm.use_streaming)
        dlg.set_relay_config(self.settings_vm.relay_ip, self.settings_vm.relay_port)
        dlg.set_save_enabled(self.settings_vm.is_valid())

    def _on_settings_saved(self, cfg: dict) -> None:
        # push back into VM
        self.settings_vm.box_urls = dict(cfg.get("box_urls", {}))
        self.settings_vm.api_keys = dict(cfg.get("api_keys", {}))
        t = cfg.get("timeouts", {}) or {}
        self.settings_vm.request_timeout_s = int(
            t.get("request_s", self.settings_vm.request_timeout_s)
        )
        self.settings_vm.download_timeout_s = int(
            t.get("download_s", self.settings_vm.download_timeout_s)
        )
        self.settings_vm.poll_interval_ms = int(
            cfg.get("poll_interval_ms", self.settings_vm.poll_interval_ms)
        )
        self.settings_vm.results_dir = (
            cfg.get("results_dir", self.settings_vm.results_dir) or "."
        )
        self.settings_vm.use_streaming = bool(
            cfg.get("use_streaming", self.settings_vm.use_streaming)
        )
        r = cfg.get("relay", {}) or {}
        self.settings_vm.relay_ip = r.get("ip", self.settings_vm.relay_ip) or ""
        self.settings_vm.relay_port = int(
            r.get("port", self.settings_vm.relay_port) or 0
        )

        # reset adapter to reflect new settings
        self._job_adapter = None
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
        if not self._current_group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        try:
            out_dir = self.uc_download(self._current_group_id, self.settings_vm.results_dir)  # type: ignore[misc]
            self.win.show_toast(f"Downloaded to {out_dir}")
        except Exception as e:
            self.win.show_toast(str(e))

    def _on_download_box_results(self, box_id: str) -> None:
        # Group ZIPs are per group; per-box filtering could be added in adapter if needed
        self._on_download_group_results()

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

    def _on_electrode_mode_changed(self, mode: str) -> None:
        try:
            self.experiment_vm.set_electrode_mode(mode)  # handled by relay later
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
        self.activity.set_updated_at("Updated")

    def _open_plot_for_well(self, well_id: str) -> None:
        self.win.show_toast(f"Open PNG for {well_id}")

    # ==================================================================
    # Polling helpers
    # ==================================================================
    def _start_polling(self) -> None:
        if self._polling_active:
            return
        self._polling_active = True
        self._schedule_poll()

    def _stop_polling(self) -> None:
        self._polling_active = False

    def _schedule_poll(self) -> None:
        if not self._polling_active:
            return
        interval = max(200, int(self.settings_vm.poll_interval_ms or 750))
        # use Tk's after to keep UI-thread safe
        self.win.after(interval, self._poll_once)

    def _poll_once(self) -> None:
        if (
            not self._polling_active
            or not self._current_group_id
            or not self._ensure_adapter()
        ):
            return
        try:
            snap = self.uc_poll(self._current_group_id)  # type: ignore[misc]
            self.progress_vm.apply_snapshot(snap)
            if snap.get("all_done"):
                self._stop_polling()
                self.win.show_toast("All runs completed.")
                return
        except Exception as e:
            self.win.show_toast(str(e))
        finally:
            self._schedule_poll()

    # ==================================================================
    # Plan building
    # ==================================================================

    def _build_plan_from_vm(self, selection: Iterable[str]) -> Dict:
        """
        Build a JobRequest-ready plan for StartExperimentBatch.
        Collects all configured wells and their stored parameters.

        The UseCase will:
        - Group wells per box and per identical signature,
        - Generate one JobRequest per (Box,Signature),
        - Estimate planned durations (mode-specific) per run.

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
        folder_name = self.settings_vm.results_dir or "."
        make_plot = True  # default: let backend create plots
        tia_gain = None  # will be added later via Settings
        sampling_interval = None  # will be added later via Settings

        # 4) Compose plan dict for the UseCase
        plan = {
            "selection": sorted(configured),
            "well_params_map": well_params_map,
            "folder_name": folder_name,
            "make_plot": make_plot,
            "tia_gain": tia_gain,
            "sampling_interval": sampling_interval,
            # "group_id": optional custom ID could be added here
        }

        # 5) Debug convenience (optional)
        print(f"[DEBUG] Built plan for {len(configured)} wells across boxes.")

        return plan


def main() -> None:
    app = App()
    app.win.mainloop()


if __name__ == "__main__":
    main()
