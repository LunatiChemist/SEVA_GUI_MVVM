"""
DataPlotter (Popup) – updated UI
--------------------------------
Tkinter Toplevel window that mirrors the original SEVA data plotting UI, but
keeps all processing (IR correction, loading/plotting/export) out of the View.
The View only raises callbacks and exposes setters for the ViewModel.

What this View provides:
- Header with RunGroupId + current selection summary
- Controls row: Fetch/Refresh, Axes (X/Y), Section, Rs (IR), Apply IR, Reset IR,
  Export CSV/PNG
- Scrollable list of wells: [Include] [Well] [PNG?] [Path] [Open PNG] [Open Folder]
- Status line with counters (loaded / corrected)
- Proper close behavior (WM_DELETE_WINDOW) and reusable instance handling

All comments in English (project guidance).
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable, Optional, Tuple, List

WellId = str


class DataPlotter(tk.Toplevel):
    """Read-only popup that lists result files and exposes plot controls."""

    # Callback types
    OnWell = Optional[callable]
    OnVoid = Optional[callable]
    OnAxes = Optional[callable]
    OnSection = Optional[callable]
    OnIR = Optional[callable]

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_fetch_data: OnVoid = None,
        on_axes_changed: OnAxes = None,         # (x_label: str, y_label: str) -> None
        on_section_changed: OnSection = None,   # (section_name: str) -> None
        on_apply_ir: OnIR = None,               # (rs_text: str) -> None
        on_reset_ir: OnVoid = None,
        on_export_csv: OnVoid = None,
        on_export_png: OnVoid = None,
        on_open_plot: OnWell = None,
        on_open_results_folder: OnWell = None,
        on_toggle_include: Optional[callable] = None,   # (well_id: str, included: bool)
        on_close: OnVoid = None,
    ) -> None:
        super().__init__(parent)
        self.title("Data Plotter")
        self.transient(parent)
        self.resizable(True, True)

        # Store callbacks
        self._on_fetch_data = on_fetch_data
        self._on_axes_changed = on_axes_changed
        self._on_section_changed = on_section_changed
        self._on_apply_ir = on_apply_ir
        self._on_reset_ir = on_reset_ir
        self._on_export_csv = on_export_csv
        self._on_export_png = on_export_png
        self._on_open_plot = on_open_plot
        self._on_open_results_folder = on_open_results_folder
        self._on_toggle_include = on_toggle_include
        self._on_close = on_close

        # Close actions
        self.protocol("WM_DELETE_WINDOW", self._on_close_clicked)

        # ---------------- Header ----------------
        header = ttk.Frame(self)
        header.pack(fill="x", padx=8, pady=(8, 4))
        self._run_var = tk.StringVar(value="Run: –")
        self._selection_var = tk.StringVar(value="Selection: –")
        ttk.Label(header, textvariable=self._run_var).pack(side="left")
        ttk.Label(header, text="   ").pack(side="left")
        ttk.Label(header, textvariable=self._selection_var).pack(side="left")

        # ---------------- Controls ----------------
        controls = ttk.Frame(self)
        controls.pack(fill="x", padx=8, pady=(0, 6))
        controls.columnconfigure(8, weight=1)

        ttk.Button(controls, text="Fetch/Refresh", command=lambda: self._safe(self._on_fetch_data)).grid(row=0, column=0, padx=(0,8))

        ttk.Label(controls, text="X").grid(row=0, column=1, sticky="e")
        self._x_var = tk.StringVar()
        self._x_combo = ttk.Combobox(controls, textvariable=self._x_var, state="readonly", width=12)
        self._x_combo.grid(row=0, column=2, padx=(4,8))
        self._x_combo.bind("<<ComboboxSelected>>", lambda e: self._emit_axes())

        ttk.Label(controls, text="Y").grid(row=0, column=3, sticky="e")
        self._y_var = tk.StringVar()
        self._y_combo = ttk.Combobox(controls, textvariable=self._y_var, state="readonly", width=12)
        self._y_combo.grid(row=0, column=4, padx=(4,12))
        self._y_combo.bind("<<ComboboxSelected>>", lambda e: self._emit_axes())

        ttk.Label(controls, text="Section").grid(row=0, column=5, sticky="e")
        self._section_var = tk.StringVar()
        self._section_combo = ttk.Combobox(controls, textvariable=self._section_var, state="readonly", width=16)
        self._section_combo.grid(row=0, column=6, padx=(4,12))
        self._section_combo.bind("<<ComboboxSelected>>", lambda e: self._emit_section())

        ttk.Label(controls, text="Rs (Ω)").grid(row=0, column=7, sticky="e")
        self._rs_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self._rs_var, width=8).grid(row=0, column=8, sticky="w")

        ttk.Button(controls, text="Apply IR", command=lambda: self._emit_ir_apply()).grid(row=0, column=9, padx=(12,4))
        ttk.Button(controls, text="Reset IR", command=lambda: self._safe(self._on_reset_ir)).grid(row=0, column=10)

        ttk.Button(controls, text="Export CSV", command=lambda: self._safe(self._on_export_csv)).grid(row=0, column=11, padx=(18,4))
        ttk.Button(controls, text="Export PNG", command=lambda: self._safe(self._on_export_png)).grid(row=0, column=12)

        # ---------------- Body: Scrollable list of wells ----------------
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(body, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")

        self._inner = ttk.Frame(self._canvas)
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(self._inner_id, width=e.width))

        # Header row for list
        header_row = ttk.Frame(self._inner)
        header_row.grid(row=0, column=0, sticky="ew", pady=(0,4))
        header_row.columnconfigure(3, weight=1)
        ttk.Label(header_row, text="Include", width=8).grid(row=0, column=0, sticky="w")
        ttk.Label(header_row, text="Well", width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(header_row, text="PNG", width=6).grid(row=0, column=2, sticky="w")
        ttk.Label(header_row, text="Path").grid(row=0, column=3, sticky="w")
        ttk.Label(header_row, text="Actions", width=20).grid(row=0, column=4, sticky="w")

        self._rows_frame = ttk.Frame(self._inner)
        self._rows_frame.grid(row=1, column=0, sticky="nsew")
        # Map WellId -> (chkvar, lbl_well, lbl_png, lbl_path, btn_open, btn_folder)
        self._rows: Dict[WellId, Tuple[tk.BooleanVar, ttk.Label, ttk.Label, ttk.Label, ttk.Button, ttk.Button]] = {}

        # ---------------- Footer / status line ----------------
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=8, pady=(0, 8))
        self._stats_var = tk.StringVar(value="Loaded: 0 • Corrected: 0")
        ttk.Label(footer, textvariable=self._stats_var).pack(side="left")

        ttk.Button(footer, text="Close", command=self._on_close_clicked).pack(side="right")

        # Focus dialog
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------
    # Public setters (called by ViewModel)
    # ------------------------------------------------------------------
    def set_run_info(self, run_group_id: Optional[str], selection_summary: str) -> None:
        self._run_var.set(f"Run: {run_group_id or '–'}")
        self._selection_var.set(f"Selection: {selection_summary or '–'}")

    def set_axes_options(self, x_options: List[str], y_options: List[str]) -> None:
        self._x_combo.configure(values=list(x_options))
        self._y_combo.configure(values=list(y_options))

    def set_selected_axes(self, x: str, y: str) -> None:
        self._x_var.set(x)
        self._y_var.set(y)

    def set_sections(self, options: List[str], selected: Optional[str] = None) -> None:
        self._section_combo.configure(values=list(options))
        if selected is not None:
            self._section_var.set(selected)

    def set_ir_params(self, rs_value: str) -> None:
        self._rs_var.set(rs_value)

    def set_rows(self, mapping: Dict[WellId, Tuple[bool, str, bool]]) -> None:
        """Replace well rows.
        mapping: WellId -> (has_png: bool, path: str, included: bool)
        """
        for c in list(self._rows_frame.winfo_children()):
            c.destroy()
        self._rows.clear()

        for r, (wid, (has, path, included)) in enumerate(sorted(mapping.items())):
            chk_var = tk.BooleanVar(value=bool(included))
            chk = ttk.Checkbutton(self._rows_frame, variable=chk_var,
                                  command=lambda w=wid, v=chk_var: self._emit_toggle_include(w, v.get()))
            lbl_well = ttk.Label(self._rows_frame, text=wid, width=8)
            lbl_png = ttk.Label(self._rows_frame, text=("Yes" if has else "No"), width=6)
            lbl_path = ttk.Label(self._rows_frame, text=path or "")
            btn_open = ttk.Button(self._rows_frame, text="Open PNG",
                                  state=(tk.NORMAL if has else tk.DISABLED),
                                  command=(lambda w=wid: self._emit_open_plot(w)))
            btn_folder = ttk.Button(self._rows_frame, text="Open Folder",
                                    command=(lambda w=wid: self._emit_open_folder(w)))

            chk.grid(row=r, column=0, sticky="w", padx=(0,8), pady=2)
            lbl_well.grid(row=r, column=1, sticky="w", padx=(0,8), pady=2)
            lbl_png.grid(row=r, column=2, sticky="w", padx=(0,8), pady=2)
            lbl_path.grid(row=r, column=3, sticky="w", padx=(0,8), pady=2)
            btn_open.grid(row=r, column=4, sticky="w", padx=(0,4), pady=2)
            btn_folder.grid(row=r, column=5, sticky="w", padx=(0,8), pady=2)

            self._rows[wid] = (chk_var, lbl_well, lbl_png, lbl_path, btn_open, btn_folder)

    def set_stats(self, loaded: int, corrected: int) -> None:
        self._stats_var.set(f"Loaded: {loaded} • Corrected: {corrected}")

    # ------------------------------------------------------------------
    # Emit helpers
    # ------------------------------------------------------------------
    def _emit_axes(self) -> None:
        if self._on_axes_changed:
            try:
                self._on_axes_changed(self._x_var.get(), self._y_var.get())
            except Exception as e:
                print(f"DataPlotter axes callback failed: {e}")

    def _emit_section(self) -> None:
        if self._on_section_changed:
            try:
                self._on_section_changed(self._section_var.get())
            except Exception as e:
                print(f"DataPlotter section callback failed: {e}")

    def _emit_ir_apply(self) -> None:
        if self._on_apply_ir:
            try:
                self._on_apply_ir(self._rs_var.get())
            except Exception as e:
                print(f"DataPlotter apply IR failed: {e}")

    def _emit_open_plot(self, well_id: WellId) -> None:
        if self._on_open_plot:
            try:
                self._on_open_plot(well_id)
            except Exception as e:
                print(f"DataPlotter open plot failed: {e}")

    def _emit_open_folder(self, well_id: WellId) -> None:
        if self._on_open_results_folder:
            try:
                self._on_open_results_folder(well_id)
            except Exception as e:
                print(f"DataPlotter open folder failed: {e}")

    def _emit_toggle_include(self, well_id: WellId, included: bool) -> None:
        if self._on_toggle_include:
            try:
                self._on_toggle_include(well_id, bool(included))
            except Exception as e:
                print(f"DataPlotter toggle include failed: {e}")

    def _on_close_clicked(self) -> None:
        if self._on_close:
            try:
                self._on_close()
            except Exception as e:
                print(f"DataPlotter on_close failed: {e}")
        self.destroy()

    # ------------------------------------------------------------------
    def _safe(self, fn: OnVoid) -> None:
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"DataPlotter callback failed: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    dp = DataPlotter(root)
    dp.set_run_info("group-123", "A1, A2, B3 (3)")
    dp.set_axes_options(["E", "E_real", "t"], ["I", "E", "dQ/dt"])
    dp.set_selected_axes("E", "I")
    dp.set_sections(["scan1", "scan2", "segment-0-100"], selected="scan1")
    dp.set_ir_params("0.0")
    dp.set_rows({"A1": (True, "./A1.png", True), "A2": (False, "", False), "B3": (True, "./B3.png", True)})
    dp.set_stats(loaded=2, corrected=0)
    root.mainloop()
