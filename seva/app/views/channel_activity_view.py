"""
ChannelActivityView
-------------------
Read-only tab that shows a compact activity matrix for all boxes (A-D) and
wells (1..10). It mirrors the visual style of the original GUI: small square
cells with color-coded status (Idle/Queued/Running/Done/Error). No backend or
validation logic lives here - this is a pure View with public setters.

Usage (from a ViewModel/presenter):
- call `set_boxes(["A","B"])` to define which boxes are visible
- call `set_activity({"A1":"Running","A2":"Idle", ...})` to update colors
- call `set_updated_at("12:03:15")` to update the timestamp label

All comments are in English per project guidance.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

WellId = str  # e.g., "A1"
BoxId = str   # e.g., "A"


class ChannelActivityView(ttk.Frame):
    """Compact, scrollable, read-only activity matrix."""

    def __init__(self, parent: tk.Widget, *, boxes: Sequence[BoxId] = ("A","B","C","D")) -> None:
        super().__init__(parent)
        self._boxes: List[BoxId] = list(boxes)
        self._wells_per_box: int = 10
        self._cells: Dict[WellId, tk.Label] = {}

        # Header with last update timestamp
        header = ttk.Frame(self)
        header.pack(fill="x", padx=6, pady=(6, 2))
        self._updated_var = tk.StringVar(value="Updated: –")
        ttk.Label(header, textvariable=self._updated_var).pack(side="left")

        # Scrollable canvas for the matrix
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=6, pady=(2, 6))
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrap, highlightthickness=0)
        vbar = ttk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        hbar = ttk.Scrollbar(wrap, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")

        self._inner = ttk.Frame(self._canvas)
        self._inner_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._build_matrix()

    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event):
        # Ensure the inner frame matches canvas width for nicer horizontal behavior
        bbox = self._canvas.bbox(self._inner_id)
        if bbox:
            self._canvas.itemconfigure(self._inner_id, width=event.width)

    def _build_matrix(self) -> None:
        """Render 4 Labelframes (A–D), each 2 columns × 5 rows of tiny cells."""
        # cleanup
        for child in list(self._inner.winfo_children()):
            child.destroy()
        self._cells.clear()

        globalindex = 1
        for col, box_id in enumerate(self._boxes):
            frame = ttk.Labelframe(self._inner, text=f"{box_id}")
            frame.grid(row=0, column=col, padx=8, pady=6, sticky="n")

            for i in range(1, self._wells_per_box + 1):
                row = (i - 1) % 5
                col2 = 0 if i <= 5 else 1
                wid = f"{box_id}{globalindex}"
                cell = tk.Label(frame, text=str(i if box_id == self._boxes[0] else ((col)*10 + i)),
                                width=4, height=1, relief="groove", bg="white")
                cell.grid(row=row, column=col2, padx=3, pady=2, sticky="nsew")
                self._cells[wid] = cell
                globalindex += 1

    # ------------------------------------------------------------------
    def set_boxes(self, boxes: Iterable[BoxId]) -> None:
        self._boxes = list(boxes)
        self._build_matrix()

    def set_activity(self, mapping: Dict[WellId, str]) -> None:
        """Update cell background colors based on status strings."""
        for wid, status in mapping.items():
            cell = self._cells.get(wid)
            if not cell:
                continue
            cell.configure(bg=self._status_to_color(status))

    def set_updated_at(self, text: str) -> None:
        self._updated_var.set(f"Updated: {text}")

    # ------------------------------------------------------------------
    @staticmethod
    def _status_to_color(status: str) -> str:
        mapping = {
            "Idle": "white",
            "Queued": "#e0f7fa",
            "Running": "#c8e6c9",
            "Done": "#bbdefb",
            "Error": "#ffcdd2",
        }
        return mapping.get(status, "white")


if __name__ == "__main__":
    root = tk.Tk()
    v = ChannelActivityView(root, boxes=("A","B"))
    v.pack(fill="both", expand=True)
    v.set_activity({"B11":"Running", "A2":"Error", "B10":"Done"})
    v.set_updated_at("12:03:15")
    root.mainloop()
