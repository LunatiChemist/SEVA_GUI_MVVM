"""
ExperimentPanelView (adjusted to original GUI layout)
----------------------------------------------------
(Tkinter View; UI-only)
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Dict



class ExperimentPanelView(ttk.Frame):
    OnVoid = Optional[Callable[[], None]]
    OnChange = Optional[Callable[[str, str], None]]

    def __init__(
        self,
        parent: tk.Widget,
        *,
        on_change: OnChange = None,
        on_toggle_control_mode: OnVoid = None,
        on_apply_params: OnVoid = None,
        on_end_task: OnVoid = None,
        on_end_selection: OnVoid = None,
        on_copy_cv: OnVoid = None,
        on_paste_cv: OnVoid = None,
        on_copy_dcac: OnVoid = None,
        on_paste_dcac: OnVoid = None,
        on_copy_cdl: OnVoid = None,
        on_paste_cdl: OnVoid = None,
        on_copy_eis: OnVoid = None,
        on_paste_eis: OnVoid = None,
        on_electrode_mode_changed: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)

        self._on_change = on_change
        self._on_toggle_control_mode = on_toggle_control_mode
        self._on_apply_params = on_apply_params
        self._on_end_task = on_end_task
        self._on_end_selection = on_end_selection
        self._on_copy_cv = on_copy_cv
        self._on_paste_cv = on_paste_cv
        self._on_copy_dcac = on_copy_dcac
        self._on_paste_dcac = on_paste_dcac
        self._on_copy_cdl = on_copy_cdl
        self._on_paste_cdl = on_paste_cdl
        self._on_copy_eis = on_copy_eis
        self._on_paste_eis = on_paste_eis
        self._on_electrode_mode_changed = on_electrode_mode_changed

        self._electrode_display = tk.StringVar(value="3-electrode")
        self._vars: Dict[str, tk.StringVar] = {}
        self._flag_vars: Dict[str, tk.BooleanVar] = {}
        self._mode_frames: Dict[str, ttk.Labelframe] = {}

        # --- Layout -----------------------------------------------------
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # CV
        self.cv_run_var = tk.BooleanVar(value=False)
        cv = ttk.Labelframe(self, text="Cyclic Voltammetry (CV)")
        self._mode_frames["CV"] = cv
        cv.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self._make_header_with_tools(cv, check_var=self.cv_run_var, check_text="Run CV",
                                     on_copy=self._on_copy_cv, on_paste=self._on_paste_cv)
        self._make_labeled_entry(cv, "Vertex 1 vs. Ref (V)", "cv.vertex1_v", 1)
        self._make_labeled_entry(cv, "Vertex 2 vs. Ref (V)", "cv.vertex2_v", 2)
        self._make_labeled_entry(cv, "Final vs. Ref (V)", "cv.final_v", 3)
        self._make_labeled_entry(cv, "Scan Rate (V/s)", "cv.scan_rate_v_s", 4)
        self._make_labeled_entry(cv, "Cycle Count", "cv.cycles", 5)
        self._register_flag("run_cv", self.cv_run_var)

        # DC/AC
        self.dc_run_var = tk.BooleanVar(value=False)
        self.ac_run_var = tk.BooleanVar(value=False)
        dcac = ttk.Labelframe(self, text="Electrolysis (DC/AC)")
        self._mode_frames["EA"] = dcac
        dcac.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        tools = ttk.Frame(dcac)
        tools.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Checkbutton(tools, text="Run DC", variable=self.dc_run_var).pack(side="left")
        ttk.Checkbutton(tools, text="Run AC", variable=self.ac_run_var).pack(side="left", padx=(8, 0))
        ttk.Button(tools, text="⎘", width=3, command=self._on_copy_dcac).pack(side="right")
        ttk.Button(tools, text="🗀", width=3, command=self._on_paste_dcac).pack(side="right")

        self._make_labeled_entry(dcac, "Duration (s)", "ea.duration_s", 1)
        self._make_labeled_entry(dcac, "Charge Cutoff (C)", "ea.charge_cutoff_c", 2)
        self._make_labeled_entry(dcac, "Voltage Cutoff (V)", "ea.voltage_cutoff_v", 3)
        self._make_labeled_entry(dcac, "Frequency (Hz)", "ea.frequency_hz", 4)
        self._register_flag("run_dc", self.dc_run_var)
        self._register_flag("run_ac", self.ac_run_var)

        ttk.Label(dcac, text="Control Mode").grid(row=5, column=0, padx=6, pady=4, sticky="w")
        self.control_mode_var = tk.StringVar(value="current (mA)")
        self.control_combo = ttk.Combobox(
            dcac, textvariable=self.control_mode_var, state="readonly",
            values=["current (mA)", "potential (V)"]
        )
        self.control_combo.grid(row=5, column=1, padx=6, pady=4, sticky="ew")

        ttk.Label(dcac, text="Target").grid(row=6, column=0, padx=6, pady=4, sticky="w")
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(dcac, textvariable=self.target_var)
        self.target_combo.grid(row=6, column=1, padx=6, pady=4, sticky="ew")

        # Register control_mode & ea.target as "normal" fields
        self._vars["control_mode"] = self.control_mode_var
        self.control_mode_var.trace_add("write",
            lambda *_: self._on_change and self._on_change("control_mode", self.control_mode_var.get()))
        self._vars["ea.target"] = self.target_var
        self.target_var.trace_add("write",
            lambda *_: self._on_change and self._on_change("ea.target", self.target_var.get()))

        # CDL
        self.cdl_eval_var = tk.BooleanVar(value=False)
        cdl = ttk.Labelframe(self, text="Capacitance (Cdl)")
        self._mode_frames["CDL"] = cdl
        cdl.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        self._make_header_with_tools(cdl, check_var=self.cdl_eval_var, check_text="Evaluate Cdl",
                                     on_copy=self._on_copy_cdl, on_paste=self._on_paste_cdl)
        self._make_labeled_entry(cdl, "Vertex A vs. Ref (V)", "cdl.vertex_a_v", 1)
        self._make_labeled_entry(cdl, "Vertex B vs. Ref (V)", "cdl.vertex_b_v", 2)
        self._register_flag("eval_cdl", self.cdl_eval_var)

        # EIS
        self.eis_run_var = tk.BooleanVar(value=False)
        eis = ttk.Labelframe(self, text="Impedance (EIS)")
        self._mode_frames["EIS"] = eis
        eis.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        self._make_header_with_tools(eis, check_var=self.eis_run_var, check_text="Run EIS",
                                     on_copy=self._on_copy_eis, on_paste=self._on_paste_eis)
        self._make_labeled_entry(eis, "Freq Start (Hz)", "eis.freq_start_hz", 1)
        self._make_labeled_entry(eis, "Freq End (Hz)", "eis.freq_end_hz", 2)
        self._make_labeled_entry(eis, "Points", "eis.points", 3)
        self._make_labeled_entry(eis, "Spacing (log/lin)", "eis.spacing", 4)
        self._register_flag("run_eis", self.eis_run_var)

        # Toggle sections initially
        self._set_section_enabled("CV",  bool(self.cv_run_var.get()))
        self._set_section_enabled("EA",  bool(self.dc_run_var.get()) or bool(self.ac_run_var.get()))
        self._set_section_enabled("EIS", bool(self.eis_run_var.get()))
        self._set_section_enabled("CDL", bool(self.cdl_eval_var.get()))

        # Footer
        footer = ttk.Frame(self)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 6))
        for idx in range(4):
            footer.columnconfigure(idx, weight=1)
        self.editing_well_var = tk.StringVar(value="–")
        ttk.Label(footer, textvariable=self.editing_well_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Update Parameters", command=self._on_apply_params).grid(
            row=0, column=1, sticky="", padx=6
        )
        ttk.Button(footer, text="End Selection", command=self._on_end_selection).grid(
            row=0, column=2, sticky="e", padx=6
        )
        ttk.Button(footer, text="End Task", command=self._on_end_task).grid(
            row=0, column=3, sticky="e", padx=6
        )

        mode_box = ttk.Labelframe(footer, text="Electrode Mode")
        mode_box.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 6))
        self._mode_combo = ttk.Combobox(
            mode_box, textvariable=self._electrode_display,
            state="readonly", values=["3-electrode", "2-electrode"], width=16
        )
        self._mode_combo.pack(padx=6, pady=4)
        self._mode_combo.bind("<<ComboboxSelected>>", lambda e: self._emit_electrode_mode())

    # --- helpers -------------------------------------------------------
    def _emit_electrode_mode(self) -> None:
        disp = (self._electrode_display.get() or "").strip()
        mode = "2E" if disp.startswith("2") else "3E"
        if self._on_electrode_mode_changed:
            self._on_electrode_mode_changed(mode)

    def _make_header_with_tools(
        self, parent: tk.Widget, *, check_var: tk.BooleanVar, check_text: str,
        on_copy: OnVoid, on_paste: OnVoid
    ) -> None:
        row = 0
        left = ttk.Frame(parent); left.grid(row=row, column=0, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(left, text=check_text, variable=check_var).pack(side="left")
        right = ttk.Frame(parent); right.grid(row=row, column=1, sticky="e", padx=6, pady=4)
        ttk.Button(right, text="⎘", width=3, command=on_copy).pack(side="right")
        ttk.Button(right, text="🗀", width=3, command=on_paste).pack(side="right")

    def _make_labeled_entry(self, parent: tk.Widget, label: str, field_id: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, padx=6, pady=2, sticky="w")
        var = tk.StringVar(); self._vars[field_id] = var
        ent = ttk.Entry(parent, textvariable=var); ent.grid(row=row, column=1, padx=6, pady=2, sticky="ew")
        parent.columnconfigure(1, weight=1)
        def _on_var_changed(*_):
            if self._on_change:
                self._on_change(field_id, var.get())
        var.trace_add("write", _on_var_changed)

    def _register_flag(self, field_id: str, var: tk.BooleanVar) -> None:
        # <- BUGFIX: register flag so clear_fields()/set_fields() apply
        self._flag_vars[field_id] = var

        def _apply():
            # 1) notify VM
            if self._on_change:
                self._on_change(field_id, "1" if var.get() else "0")
            # 2) toggle section
            if field_id == "run_cv":
                self._set_section_enabled("CV", bool(var.get()))
            elif field_id == "run_dc":
                self._set_section_enabled("EA", bool(var.get()) or bool(self.ac_run_var.get()))
            elif field_id == "run_ac":
                self._set_section_enabled("EA", bool(var.get()) or bool(self.dc_run_var.get()))
            elif field_id == "run_eis":
                self._set_section_enabled("EIS", bool(var.get()))
            elif field_id == "eval_cdl":
                self._set_section_enabled("CDL", bool(var.get()))

        _apply()
        var.trace_add("write", lambda *_: _apply())

    def _set_section_enabled(self, section_key: str, enabled: bool) -> None:
        frame = self._mode_frames.get(section_key)
        if not frame:
            return
        state = "normal" if enabled else "disabled"

        def _walk(w):
            for child in w.winfo_children():
                try:
                    if isinstance(child, (ttk.Entry, ttk.Combobox)):
                        child.configure(state=state)
                except Exception:
                    pass
                _walk(child)
        _walk(frame)

    # --- Public setters ------------------------------------------------
    def set_editing_well(self, well_label: str) -> None:
        self.editing_well_var.set(f"Editing Well: {well_label}")

    def set_electrode_mode(self, mode: str) -> None:
        self._electrode_display.set("2-electrode" if mode == "2E" else "3-electrode")

    def get_electrode_mode(self) -> str:
        disp = (self._electrode_display.get() or "").strip()
        return "2E" if disp.startswith("2") else "3E"

    def set_fields(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return
        # Text fields
        for fid, var in self._vars.items():
            if fid in mapping:
                val = mapping.get(fid)
                var.set("" if val is None else str(val))
        # Flags – ALLE bekannten Flags deterministisch setzen
        def _as_bool(v: object) -> bool:
            if isinstance(v, bool):
                return v
            return str(v or "").strip().lower() in ("1", "true", "yes", "on")
        for fid, var in self._flag_vars.items():
            var.set(_as_bool(mapping.get(fid, False)))

    def clear_fields(self) -> None:
        for var in self._vars.values():
            var.set("")
        for var in self._flag_vars.values():
            var.set(False)
