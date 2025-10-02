"""
SEVA GUI – minimal bootstrap (UI-only)
-------------------------------------
Wires Views together so you can preview layout and callback flow.
No domain logic or HTTP calls here.
"""

from __future__ import annotations
import tkinter as tk
from typing import Set

# Views
from views.main_window import MainWindowView
from views.well_grid_view import WellGridView
from views.experiment_panel_view import ExperimentPanelView
from views.run_overview_view import RunOverviewView
from views.channel_activity_view import ChannelActivityView
from views.settings_dialog import SettingsDialog
from views.data_plotter import DataPlotter

print("easter_egg_here_Hello_world")

# ---- Simple in-memory demo state (standing in for ViewModels) ----
class DemoState:
    def __init__(self) -> None:
        self.selected_wells: Set[str] = set()
        self.run_group_id: str | None = None
        # View references (so we can call setters directly)
        self.root: MainWindowView | None = None
        self.wellgrid: WellGridView | None = None
        self.exp_panel: ExperimentPanelView | None = None
        self.run_overview: RunOverviewView | None = None
        self.ch_activity: ChannelActivityView | None = None
        self.settings_dialog: SettingsDialog | None = None
        self.data_plotter: DataPlotter | None = None


state = DemoState()


def main() -> None:
    win = MainWindowView(
        on_submit=on_submit,
        on_cancel_group=on_cancel_group,
        on_cancel_selection=on_cancel_selection,
        on_save_layout=on_save_layout,
        on_load_layout=on_load_layout,
        on_open_settings=on_open_settings,
        on_open_data_plotter=on_open_data_plotter,
    )

    # --- Build child views ---
    wellgrid = WellGridView(
        win.wellgrid_host,
        boxes=("A", "B", "C"),  # dynamic; adjust as needed
        on_select_wells=on_select_wells,
        on_toggle_enable_selected=lambda: info("Enable/Disable toggled for selection"),
        on_copy_params_from=lambda wid: info(f"Copy params from {wid}"),
        on_paste_params_to_selection=lambda: info("Paste params to selection"),
        on_reset_selected=lambda: info("Reset selection"),
        on_open_plot=lambda wid: info(f"Open PNG for {wid}"),
    )
    wellgrid.pack(fill="both", expand=True)
    # If your MainWindowView has a mount helper, keep it; otherwise this is enough:
    if hasattr(win, "mount_wellgrid"):
        win.mount_wellgrid(wellgrid)

    exp_panel = ExperimentPanelView(
        win.tab_experiment,
        on_change=lambda fid, val: win.set_status_message(f"Changed {fid} = {val}"),
        on_toggle_control_mode=lambda: info("Control mode toggled"),
        # Mark selected wells as "configured" (green) when user applies params
        on_apply_params=lambda: apply_params_to_selection(win),
        on_end_task=lambda: info("End task requested"),
        on_copy_cv=lambda: info("Copy CV"),
        on_paste_cv=lambda: info("Paste CV"),
        on_copy_dcac=lambda: info("Copy DC/AC"),
        on_paste_dcac=lambda: info("Paste DC/AC"),
        on_copy_cdl=lambda: info("Copy CDL"),
        on_paste_cdl=lambda: info("Paste CDL"),
    )
    win.mount_experiment_panel(exp_panel)

    run_overview = RunOverviewView(
        win.tab_run_overview,
        boxes=("A", "B", "C"),
        on_cancel_group=on_cancel_group,
        on_cancel_selection=on_cancel_selection,
        on_download_group_results=lambda: info("Download group results"),
        on_download_box_results=lambda box: info(f"Download results for Box {box}"),
        on_open_plot=lambda wid: info(f"Open PNG for {wid}"),
    )
    win.mount_run_overview(run_overview)

    ch_activity = ChannelActivityView(win.tab_channel_activity, boxes=("A", "B", "C"))
    win.mount_channel_activity(ch_activity)

    # Keep references
    state.root = win
    state.wellgrid = wellgrid
    state.exp_panel = exp_panel
    state.run_overview = run_overview
    state.ch_activity = ch_activity
    state.settings_dialog = None
    state.data_plotter = None

    # --- Seed some demo data ---
    win.set_status_message("Ready.")
    win.set_run_group_id(None)

    ch_activity.set_activity({"A1": "Running", "B3": "Error", "C10": "Done"})
    ch_activity.set_updated_at("now")

    run_overview.set_box_status("A", phase="Running", progress_pct=25, sub_run_id="run-A-001")
    run_overview.set_box_status("B", phase="Queued", progress_pct=0, sub_run_id="run-B-001")
    run_overview.set_box_status("C", phase="Idle", progress_pct=0, sub_run_id=None)
    rows = [
        ("A1", "Running", 40, "", "run-A-001"),
        ("A2", "Queued", 0, "", "run-A-001"),
        ("B3", "Error", 10, "Overvoltage", "run-B-001"),
        ("C10", "Done", 100, "", "run-C-001"),
    ]
    run_overview.set_well_rows(rows)

    win.mainloop()


# ---- Callback handlers (stand-ins for ViewModel methods) ----

def apply_params_to_selection(win: MainWindowView) -> None:
    """UI-only: mark current selection as 'configured' (green)."""
    if state.wellgrid:
        state.wellgrid.add_configured_wells(state.selected_wells)
    win.set_status_message(f"Applied params to {len(state.selected_wells)} well(s).")


def on_submit() -> None:
    """Start batch: reset ALL configured wells back to default (grey)."""
    if state.wellgrid:
        state.wellgrid.clear_all_configured()     # <- alles zurücksetzen
        state.wellgrid.set_selection(set())       # (optional) Auswahl leeren
    if state.root:
        state.root.set_status_message("Batch submitted.")


def on_cancel_group() -> None:
    if state.root:
        state.root.set_status_message("Cancel group requested.")


def on_cancel_selection() -> None:
    if state.root:
        state.root.set_status_message("Cancel selection requested.")


def on_save_layout() -> None:
    info("Save plate layout")


def on_load_layout() -> None:
    info("Load plate layout")


def on_open_settings() -> None:
    # Reuse an existing dialog if open
    if state.settings_dialog and state.settings_dialog.winfo_exists():
        state.settings_dialog.lift()
        return

    dlg = SettingsDialog(
        state.root,  # parent = main window
        on_test_connection=lambda box_id: info(f"Test box {box_id}"),
        on_test_relay=lambda: info("Test relay"),
        on_browse_results_dir=lambda: info("Browse results dir"),
        on_save=lambda settings: info(f"Save settings: {settings}"),
        on_cancel=close_settings_dialog,
    )
    state.settings_dialog = dlg


def close_settings_dialog() -> None:
    try:
        if state.settings_dialog and state.settings_dialog.winfo_exists():
            state.settings_dialog.destroy()
    finally:
        state.settings_dialog = None


def on_open_data_plotter() -> None:
    # Reuse if already open
    if state.data_plotter and state.data_plotter.winfo_exists():
        state.data_plotter.lift()
        return

    dp = DataPlotter(
        state.root,
        on_fetch_data=lambda: info("Fetch/Refresh plots"),
        on_axes_changed=lambda x, y: info(f"Axes: {x} vs {y}"),
        on_section_changed=lambda s: info(f"Section: {s}"),
        on_apply_ir=lambda rs: info(f"Apply IR with Rs={rs}"),
        on_reset_ir=lambda: info("Reset IR"),
        on_export_csv=lambda: info("Export CSV"),
        on_export_png=lambda: info("Export PNG"),
        on_open_plot=lambda wid: info(f"Open PNG for {wid}"),
        on_open_results_folder=lambda wid: info(f"Open folder for {wid}"),
        on_toggle_include=lambda wid, inc: info(f"Include {wid} = {inc}"),
        on_close=close_data_plotter,
    )

    # Demo header + rows + axes
    dp.set_run_info(state.run_group_id, ", ".join(sorted(state.selected_wells)) or "–")
    dp.set_axes_options(["E", "E_real", "t"], ["I", "E"])
    dp.set_selected_axes("E", "I")
    dp.set_sections(["scan1", "scan2"], selected="scan1")
    dp.set_ir_params("0.0")
    dp.set_rows({
        "A1": (True, "./A1.png", True),
        "B3": (False, "", False),
        "C10": (True, "./C10.png", True),
    })
    dp.set_stats(loaded=2, corrected=0)

    state.data_plotter = dp


def close_data_plotter() -> None:
    try:
        if state.data_plotter and state.data_plotter.winfo_exists():
            state.data_plotter.destroy()
    finally:
        state.data_plotter = None


def on_select_wells(wells: Set[str]) -> None:
    """Keep selection in state and reflect it in the ExperimentPanel footer."""
    state.selected_wells = set(wells)
    sample = next(iter(state.selected_wells), None)
    if state.exp_panel:
        state.exp_panel.set_editing_well(sample or "–")
        # If your ExperimentPanel has a selection count label:
        if hasattr(state.exp_panel, "set_selection_count"):
            state.exp_panel.set_selection_count(len(state.selected_wells))
    info(f"Selected wells: {sorted(state.selected_wells)}")


def info(msg: str) -> None:
    print(msg)


if __name__ == "__main__":
    main()
