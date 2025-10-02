"""
RunOverviewView
----------------
UI-only Tkinter view that displays progress/status for the current Run Group.

Features:
- Per-box summary panels (A–D) with status label, progress bar and SubRunId.
- Per-well table (Treeview) showing Phase, Progress %, Last Error, SubRunId.
- Toolbar with actions: Cancel Group, Cancel Selection, Download Group, Download per Box.
- Scrollable table; no backend or domain logic here.

All comments are in English as per project guidance.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable, List, Optional, Tuple

BoxId = str   # e.g., "A"
WellId = str  # e.g., "A1"


class RunOverviewView(ttk.Frame):
    """View for monitoring a run group (status per box and per well)."""

    # ---- Callback types ----
    OnVoid = Optional[callable]
    OnBox = Optional[callable]

    def __init__(
        self,
        parent: tk.Widget,
        *,
        boxes: Iterable[BoxId] = ("A", "B", "C", "D"),
        on_cancel_group: OnVoid = None,
        on_cancel_selection: OnVoid = None,
        on_download_group_results: OnVoid = None,
        on_download_box_results: OnBox = None,
        on_open_plot: Optional[callable] = None,
    ) -> None:
        super().__init__(parent)

        self._boxes = list(boxes)
        self._on_cancel_group = on_cancel_group
        self._on_cancel_selection = on_cancel_selection
        self._on_download_group_results = on_download_group_results
        self._on_download_box_results = on_download_box_results
        self._on_open_plot = on_open_plot

        # Layout rows: toolbar, box summary, well table
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_box_summary()
        self._build_well_table()

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        ttk.Button(bar, text="Cancel Group", command=lambda: self._safe(self._on_cancel_group)).pack(side="left")
        ttk.Button(bar, text="Cancel Selection", command=lambda: self._safe(self._on_cancel_selection)).pack(side="left", padx=6)
        ttk.Button(bar, text="Download Group", command=lambda: self._safe(self._on_download_group_results)).pack(side="left", padx=18)

        # Spacer
        ttk.Label(bar, text="").pack(side="left", padx=6)

        # Per-box download buttons on the right
        right = ttk.Frame(bar)
        right.pack(side="right")
        for b in self._boxes:
            ttk.Button(right, text=f"Download Box {b}", command=lambda bid=b: self._safe_box(bid)).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    def _build_box_summary(self) -> None:
        wrap = ttk.Frame(self)
        wrap.grid(row=1, column=0, sticky="ew", padx=6, pady=4)

        self._box_cards: Dict[BoxId, ttk.Frame] = {}
        self._box_status_lbl: Dict[BoxId, ttk.Label] = {}
        self._box_prog: Dict[BoxId, ttk.Progressbar] = {}
        self._box_subrun: Dict[BoxId, ttk.Label] = {}

        for idx, b in enumerate(self._boxes):
            card = ttk.Labelframe(wrap, text=f"Box {b}")
            card.grid(row=0, column=idx, padx=6, pady=2, sticky="ew")
            card.columnconfigure(1, weight=1)
            self._box_cards[b] = card

            ttk.Label(card, text="Status:").grid(row=0, column=0, sticky="w", padx=6, pady=2)
            self._box_status_lbl[b] = ttk.Label(card, text="Idle")
            self._box_status_lbl[b].grid(row=0, column=1, sticky="w", padx=6, pady=2)

            self._box_prog[b] = ttk.Progressbar(card, mode="determinate", maximum=100, value=0)
            self._box_prog[b].grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(2, 6))

            ttk.Label(card, text="SubRunId:").grid(row=2, column=0, sticky="w", padx=6)
            self._box_subrun[b] = ttk.Label(card, text="–")
            self._box_subrun[b].grid(row=2, column=1, sticky="w", padx=6)

    # ------------------------------------------------------------------
    def _build_well_table(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=(4, 6))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("well", "phase", "progress", "error", "subrun")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.table.heading("well", text="Well")
        self.table.heading("phase", text="Phase")
        self.table.heading("progress", text="Progress %")
        self.table.heading("error", text="Last Error")
        self.table.heading("subrun", text="SubRunId")

        self.table.column("well", width=60, anchor="center")
        self.table.column("phase", width=120, anchor="w")
        self.table.column("progress", width=90, anchor="e")
        self.table.column("error", width=300, anchor="w")
        self.table.column("subrun", width=140, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.table.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Public API used by ViewModels/Presenters
    # ------------------------------------------------------------------
    def set_box_status(self, box_id: BoxId, *, phase: str, progress_pct: float, sub_run_id: Optional[str]) -> None:
        """Update per-box summary information."""
        if box_id not in self._boxes:
            return
        self._box_status_lbl[box_id].configure(text=phase)
        try:
            pct = max(0, min(100, float(progress_pct)))
        except Exception:
            pct = 0
        self._box_prog[box_id].configure(value=pct)
        self._box_subrun[box_id].configure(text=sub_run_id or "–")

    def set_well_rows(self, rows: List[Tuple[WellId, str, float, str, Optional[str]]]) -> None:
        """Replace the well table content.

        rows: list of tuples (well_id, phase, progress_pct, last_error, sub_run_id)
        """
        self.table.delete(*self.table.get_children())
        for (well, phase, progress, err, subrun) in rows:
            try:
                progress_str = f"{float(progress):.0f}"
            except Exception:
                progress_str = ""
            self.table.insert("", "end", values=(well, phase, progress_str, err or "", subrun or ""))

    def set_boxes(self, boxes: Iterable[BoxId]) -> None:
        """Rebuild summary header for a new set of boxes."""
        # Destroy and rebuild summary area
        for child in list(self.grid_slaves(row=1, column=0)):
            child.destroy()
        self._boxes = list(boxes)
        self._build_box_summary()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _safe(self, fn: Optional[callable]):
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"RunOverviewView callback failed: {e}")

    def _safe_box(self, box_id: BoxId):
        if self._on_download_box_results:
            try:
                self._on_download_box_results(box_id)
            except Exception as e:
                print(f"RunOverviewView download box failed: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    view = RunOverviewView(root, boxes=("A","B","C"))
    view.pack(fill="both", expand=True)
    view.set_box_status("A", phase="Running", progress_pct=42, sub_run_id="runA-123")
    view.set_box_status("B", phase="Queued", progress_pct=0, sub_run_id=None)
    rows = [("A1","Running",40,"","runA-123"),("A2","Error",10,"Overvoltage","runA-123"),("B1","Queued",0,"","")]
    view.set_well_rows(rows)
    root.mainloop()
