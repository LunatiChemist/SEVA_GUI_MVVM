"""Run overview tab that renders per-box and per-well runtime status.

This module is view-only. It receives already-prepared DTO tuples from the
progress viewmodel and renders them in summary cards plus a details table.
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
        on_download_group_results: OnVoid = None,
        on_download_box_results: OnBox = None,
        on_open_plot: Optional[callable] = None,
    ) -> None:
        """Create toolbar, box summary cards, and well status table.

        Args:
            parent: Notebook tab container.
            boxes: Ordered list of box ids shown in summary cards.
            on_cancel_group: Optional cancel-group callback (reserved).
            on_download_group_results: Callback for group download action.
            on_download_box_results: Optional callback for box-scoped download.
            on_open_plot: Optional callback used by row interactions.
        """
        super().__init__(parent)

        self._boxes = list(boxes)
        self._on_cancel_group = on_cancel_group
        self._on_download_group_results = on_download_group_results
        self._on_open_plot = on_open_plot

        # Layout rows: toolbar, box summary, well table
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_toolbar()
        self._build_box_summary()
        self._build_well_table()

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        """Build row of top-level actions for the run overview tab."""
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        ttk.Button(bar, text="Download Group", command=self._on_download_group_results).pack(side="left", padx=18)

    # ------------------------------------------------------------------
    def _build_box_summary(self) -> None:
        """Build per-box status card widgets."""
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
        """Build scrollable tree table for per-well status rows."""
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=(4, 6))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        columns = ("well", "phase", "current_mode", "next_modes" ,"progress", "remaining", "error", "subrun")
        self.table = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        self.table.heading("well", text="Well")
        self.table.heading("phase", text="Phase")
        self.table.heading("current_mode", text="Current Mode")
        self.table.heading("next_modes", text="Next Modes")
        self.table.heading("progress", text="Progress %")
        self.table.heading("remaining", text="Remaining")
        self.table.heading("error", text="Last Error")
        self.table.heading("subrun", text="SubRunId")

        self.table.column("well", width=60, anchor="center")
        self.table.column("phase", width=120, anchor="w")
        self.table.column("current_mode", width=60, anchor="center")
        self.table.column("next_modes", width=120, anchor="center")
        self.table.column("progress", width=90, anchor="e")
        self.table.column("remaining", width=100, anchor="e")
        self.table.column("error", width=300, anchor="w")
        self.table.column("subrun", width=140, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.table.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Selection shows full error in details; double-click opens modal
        self.table.bind("<Double-1>", self._on_row_double_click)

    # ------------------------------------------------------------------
    # Public API used by ViewModels/Presenters
    # ------------------------------------------------------------------
    def set_box_status(self, box_id: BoxId, *, phase: str, progress_pct: float, sub_run_id: Optional[str]) -> None:
        """Update one box card with latest phase/progress/subrun values.

        Args:
            box_id: Box identifier to update.
            phase: User-facing phase text.
            progress_pct: Progress percent value from 0 to 100.
            sub_run_id: Optional sub-run identifier label.
        """
        if box_id not in self._boxes:
            return
        self._box_status_lbl[box_id].configure(text=phase)
        pct = max(0, min(100, float(progress_pct)))
        self._box_prog[box_id].configure(value=pct)
        self._box_subrun[box_id].configure(text=sub_run_id or "–")

    def set_well_rows(self, rows: List[Tuple]) -> None:
        """Replace the well table content.

        Args:
            rows: Iterable of table tuples in presenter/viewmodel format.
        """
        self.table.delete(*self.table.get_children())
        for row in rows:
            well, phase, current_mode, next_modes, progress, remaining, err, subrun = row

            progress_str = f"{float(progress):.0f}"
            remaining_str = self._format_remaining(remaining)
            self.table.insert(
                "",
                "end",
                values=(well or "", phase or "", current_mode or "", next_modes or "",
                        progress_str, remaining_str, err or "", subrun or ""),
            )

    def set_boxes(self, boxes: Iterable[BoxId]) -> None:
        """Rebuild summary header for a new set of boxes.

        Args:
            boxes: New ordered set of visible boxes.
        """
        # Destroy and rebuild summary area
        for child in list(self.grid_slaves(row=1, column=0)):
            child.destroy()
        self._boxes = list(boxes)
        self._build_box_summary()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _format_remaining(self, remaining: Optional[object]) -> str:
        """Normalize remaining-time values for table display.

        Args:
            remaining: Remaining value from DTO.
        """
        text = "" if remaining is None else str(remaining).strip()
        return text or "—"

    def _on_row_double_click(self, event=None):
        """Open modal with full error text for the selected row.

        Args:
            event: Tk double-click event (unused).
        """
        sel = self.table.selection()
        if not sel:
            return
        item = self.table.item(sel[0])
        vals = item.get("values") or []
        full_err = vals[6] if len(vals) > 6 else ""
        if not full_err:
            return

        top = tk.Toplevel(self)
        top.title("Full Error")
        top.geometry("700x400")
        top.transient(self.winfo_toplevel())
        frm = ttk.Frame(top)
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        txt = tk.Text(frm, wrap="word")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", full_err)
        txt.configure(state="disabled")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(6,0))
        ttk.Button(btns, text="Copy", command=lambda: self._copy_to_clipboard(full_err)).pack(side="left")
        ttk.Button(btns, text="Close", command=top.destroy).pack(side="right")

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard.

        Args:
            text: Text payload copied when user clicks "Copy" in the error modal.
        """
        self.clipboard_clear()
        self.clipboard_append(text or "")

if __name__ == "__main__":
    root = tk.Tk()
    view = RunOverviewView(root, boxes=("A","B","C","D"))
    view.pack(fill="both", expand=True)
    view.set_box_status("A", phase="Running", progress_pct=52, sub_run_id="runA-1123")
    view.set_box_status("B", phase="Running", progress_pct=85, sub_run_id="runA-1323")
    view.set_box_status("C", phase="Idle", progress_pct=0, sub_run_id=None)
    view.set_box_status("D", phase="Running", progress_pct=50, sub_run_id="runA-1213")
    rows = [
        ("A1", "Running", "CV", ["EIS", "CDL"], 40, "00:12:00", "", "runA-1123"),
        (
            "A2",
            "Error",
            "CV",
            ["EIS", "CDL"],
            10,
            "00:27:30",
            "Overvoltage",
            "runA-1123",
        ),
        ("B11", "Done", "", "", 100, "—", "", "runA-1323"),
        ("B16", "Running", "EIS", "", 85, "00:01:14", "", "runA-1323"),
        ("D33", "Running", "EIS", "", 91, "00:01:54", "", "runA-1213"),
        ("D34", "Running", "CV", "", 59, "00:12:45", "", "runA-1213"),
        ("D37", "Running", "CV", "EIS", 47, "00:10:79", "", "runA-1213"),
    ]
    view.set_well_rows(rows)
    root.mainloop()
