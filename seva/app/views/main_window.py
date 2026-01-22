"""
MainWindowView
---------------
Tkinter main window for the SEVA GUI following MVVM + Hexagonal architecture.
This file contains **only View code** – no HTTP, no domain logic. It exposes
callback hooks that are expected to be connected to ViewModels.

Author: (you)
Notes:
- Keep all comments in English (per project guidance).
- The window provides:
  * Toolbar with core actions
  * Left area for WellGridView (inserted later)
  * Right Notebook with tabs: Experiment, Run Overview, Channel Activity
  * StatusBar at the bottom
- All external interactions are signaled via callbacks passed to the constructor.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class MainWindowView(tk.Tk):
    """Top-level application window.

    This class is UI-only. It defines layout containers and wires UI events to
    callbacks provided by ViewModels (or a simple presenter). The child views
    (WellGridView, ExperimentPanelView, RunOverviewView, ChannelActivityTab)
    will be created and inserted later.
    """

    # ---- Callback type aliases (callables injected from ViewModels) ----
    OnVoid = Optional[Callable[[], None]]

    def __init__(
        self,
        *,
        on_submit: OnVoid = None,
        on_cancel_group: OnVoid = None,
        on_save_layout: OnVoid = None,
        on_load_layout: OnVoid = None,
        on_open_settings: OnVoid = None,
        on_open_data_plotter: OnVoid = None,
    ) -> None:
        super().__init__()

        # ---- Window basics ----
        self.title("SEVA – Potentiostat GUI")
        self.geometry("1280x800")  # default size; user can resize
        self.minsize(1000, 700)

        # Keep references to callbacks (can be None; we guard before calling)
        self._on_submit = on_submit
        self._on_cancel_group = on_cancel_group
        self._on_save_layout = on_save_layout
        self._on_load_layout = on_load_layout
        self._on_open_settings = on_open_settings
        self._on_open_data_plotter = on_open_data_plotter

        # ---- High-level layout: 3 rows (Toolbar, Main, Status) ----
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_toolbar(self)
        self._build_main_area(self)
        self._build_statusbar(self)

        # Keyboard shortcuts (lightweight, can be extended)
        self.bind("<Control-Return>", lambda e: self._on_submit and self._on_submit())
        self.bind("<Control-s>", lambda e: self._on_save_layout and self._on_save_layout())
        self.bind("<Control-o>", lambda e: self._on_load_layout and self._on_load_layout())

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _build_toolbar(self, parent: tk.Widget) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        toolbar.columnconfigure(tuple(range(10)), weight=0)

        # Primary actions
        ttk.Button(toolbar, text="Start", command=self._on_submit).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Cancel Group", command=self._on_cancel_group).grid(
            row=0, column=1, padx=6
        )

        # Layout presets
        ttk.Button(toolbar, text="Save Layout", command=self._on_save_layout).grid(
            row=0, column=2, padx=(24, 6)
        )
        ttk.Button(toolbar, text="Load Layout", command=self._on_load_layout).grid(
            row=0, column=3, padx=6
        )

        # Tools / Settings
        ttk.Button(toolbar, text="Settings", command=self._on_open_settings).grid(
            row=0, column=4, padx=(24, 6)
        )
        ttk.Button(toolbar, text="Data Plotter", command=self._on_open_data_plotter).grid(
            row=0, column=5, padx=6
        )

    # ------------------------------------------------------------------
    # Main Area (split: left WellGrid, right Notebook)
    # ------------------------------------------------------------------
    def _build_main_area(self, parent: tk.Widget) -> None:
        # Static container (no scrollbar for now)
        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        # Two columns: left WellGrid, right Notebook
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Left: host frame for the WellGrid (no own scrollbars anymore)
        self.wellgrid_host = ttk.Frame(content)
        self.wellgrid_host.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Right: Notebook with tabs (Experiment / Run Overview / Channel Activity)
        self.tabs = ttk.Notebook(content)
        self.tabs.grid(row=0, column=1, sticky="nsew")

        self.tab_experiment = ttk.Frame(self.tabs)
        self.tab_run_overview = ttk.Frame(self.tabs)
        self.tab_channel_activity = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_experiment, text="Experiment")
        self.tabs.add(self.tab_run_overview, text="Run Overview")
        self.tabs.add(self.tab_channel_activity, text="Channel Activity")

        # Optional placeholders (can be removed)
        ttk.Label(self.tab_experiment, text="Experiment Panel goes here").pack(padx=16, pady=16)
        ttk.Label(self.tab_run_overview, text="Run Overview goes here").pack(padx=16, pady=16)
        ttk.Label(self.tab_channel_activity, text="Channel Activity goes here").pack(padx=16, pady=16)


    def _make_scroll_host(self, parent: tk.Widget):
        """
        Create a scrollable host frame using Canvas + inner Frame pattern.
        Returns (outer, inner):
        - outer: frame to grid in the layout (contains canvas + scrollbars)
        - inner: content frame where children (WellGridView) are packed/gridded
        """
        outer = ttk.Frame(parent)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else 0
            canvas.yview_scroll(delta, "units")

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_configure)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return outer, inner

    # ------------------------------------------------------------------
    # StatusBar
    # ------------------------------------------------------------------
    def _build_statusbar(self, parent: tk.Widget) -> None:
        status = ttk.Frame(parent)
        status.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))
        status.columnconfigure(1, weight=1)

        ttk.Label(status, text="Run:").grid(row=0, column=0, sticky="w")
        self.lbl_run_id = ttk.Label(status, text="-")
        self.lbl_run_id.grid(row=0, column=1, sticky="w")

        # Relay area (badges per box; created on first use)
        self._relay_area = ttk.Frame(status)
        self._relay_area.grid(row=0, column=2, sticky="w", padx=(12, 0))
        self._relay_labels = {}  # type: dict[str, ttk.Label]

        self.status_message_var = tk.StringVar(value="Ready.")
        ttk.Label(status, textvariable=self.status_message_var).grid(row=0, column=3, sticky="e")

    # ------------------------------------------------------------------
    # Public API (called by VMs/presenters)
    # ------------------------------------------------------------------
    def set_status_message(self, text: str) -> None:
        """Update the short status message shown in the status bar."""
        self.status_message_var.set(text)

    def set_run_group_id(self, run_id: Optional[str]) -> None:
        """Display current RunGroupId (or a dash if None)."""
        self.lbl_run_id.configure(text=run_id or "–")

    def mount_wellgrid(self, view: tk.Widget) -> None:
        """Mount the WellGridView into the left scroll host.

        Usage: create your WellGridView with parent=self.wellgrid_host.
        """
        # The host returns a frame; children can be gridded/packed by the caller.
        # We keep this API for clarity; nothing to do here for now.
        pass

    def set_relay_status(self, box_id: str, status: str) -> None:
        """
        Update relay reachability indicator for a box.
        status: 'OK' | 'Fail' | 'Unknown'
        """
        # Create label lazily
        if box_id not in self._relay_labels:
            lbl = ttk.Label(self._relay_area, text=f"{box_id}: ?")
            lbl.pack(side="left", padx=4)
            self._relay_labels[box_id] = lbl

        lbl = self._relay_labels[box_id]
        text = f"{box_id}: {status}"
        lbl.configure(text=text)

    def show_toast(self, message: str, level: str = "info") -> None:
        """
        Lightweight user feedback in the statusbar.
        level is currently informational; styling could be extended later.
        """
        self.status_message_var.set(message)

    def mount_experiment_panel(self, view: tk.Widget) -> None:
        """Replace placeholder with the real ExperimentPanel view."""
        for child in list(self.tab_experiment.winfo_children()):
            if child is view:
                continue
            child.destroy()
        # Pack only if not already managed
        try:
            view.pack_info()
        except Exception:
            view.pack(fill="both", expand=True)

    def mount_run_overview(self, view: tk.Widget) -> None:
        """Replace placeholder with the real RunOverview view."""
        for child in list(self.tab_run_overview.winfo_children()):
            if child is view:
                continue
            child.destroy()
        try:
            view.pack_info()
        except Exception:
            view.pack(fill="both", expand=True)

    def mount_channel_activity(self, view: tk.Widget) -> None:
        """Replace placeholder with the real ChannelActivity view."""
        for child in list(self.tab_channel_activity.winfo_children()):
            if child is view:
                continue
            child.destroy()
        try:
            view.pack_info()
        except Exception:
            view.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal manual preview (no real callbacks wired). This block can be removed
    # in production; it is useful during early UI iteration.
    win = MainWindowView()
    win.mainloop()
