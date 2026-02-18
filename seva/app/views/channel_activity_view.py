"""Read-only activity matrix view for box/well status rendering.

This view renders an A/B/C/... matrix of small status cells and exposes
setter-style methods used by progress viewmodels. It performs no I/O.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

WellId = str  # e.g., "A1"
BoxId = str   # e.g., "A"


class ChannelActivityView(ttk.Frame):
    """Compact, scrollable, read-only activity matrix."""

    _STATUS_COLORS: Dict[str, str] = {
        "Idle": "#ffffff",
        "Queued": "#e6f4ff",
        "Running": "#d5f5de",
        "Done": "#d9e4ff",
        "Error": "#ffdce0",
    }

    def __init__(self, parent: tk.Widget, *, boxes: Sequence[BoxId] = ("A","B","C","D")) -> None:
        """Build matrix tab widgets.

        Args:
            parent: Notebook tab container.
            boxes: Ordered list of box identifiers to render.
        """
        super().__init__(parent)
        self._boxes: List[BoxId] = list(boxes)
        self._wells_per_box: int = 10
        self._cells: Dict[WellId, tk.Label] = {}

        # Header with last update timestamp
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=10, pady=(10, 4), ipady=4)
        self._updated_var = tk.StringVar(value="Updated at --:--:--")
        ttk.Label(header, text="Channel Activity", style="Title.TLabel").pack(side="left", padx=(8, 16))
        ttk.Label(header, textvariable=self._updated_var, style="Subtle.TLabel").pack(side="left")

        # Scrollable canvas for the matrix
        wrap = ttk.Frame(self, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=10, pady=(2, 10))
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
        """Keep inner matrix width aligned to visible canvas width.

        Args:
            event: Tk configure event from the canvas.
        """
        # Ensure the inner frame matches canvas width for nicer horizontal behavior
        bbox = self._canvas.bbox(self._inner_id)
        if bbox:
            self._canvas.itemconfigure(self._inner_id, width=event.width)

    def _build_matrix(self) -> None:
        """Render one labelframe per box, each with 10 cell widgets and a legend."""
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
                                width=5, height=1, relief="groove", bg="#ffffff")
                cell.grid(row=row, column=col2, padx=3, pady=2, sticky="nsew")
                self._cells[wid] = cell
                globalindex += 1

        self._build_legend(row=1, columnspan=max(len(self._boxes), 1))

    def _build_legend(self, *, row: int, columnspan: int) -> None:
        """Render a color legend below the channel boxes."""
        legend = ttk.LabelFrame(self._inner, text="Legend")
        legend.grid(row=row, column=0, columnspan=columnspan, padx=8, pady=(0, 8), sticky="ew")

        for index, (status, color) in enumerate(self._STATUS_COLORS.items()):
            item = ttk.Frame(legend)
            item.grid(row=0, column=index, padx=8, pady=6, sticky="w")

            color_box = tk.Label(item, width=2, relief="groove", bg=color)
            color_box.pack(side="left", padx=(0, 4))
            ttk.Label(item, text=status).pack(side="left")

    # ------------------------------------------------------------------
    def set_boxes(self, boxes: Iterable[BoxId]) -> None:
        """Replace visible box set and rebuild matrix widgets.

        Args:
            boxes: Ordered iterable of box ids to render.
        """
        self._boxes = list(boxes)
        self._build_matrix()

    def set_activity(self, mapping: Dict[WellId, str]) -> None:
        """Apply well-status colors to visible cells.

        Args:
            mapping: Mapping of ``well_id -> status``.
        """
        for wid, status in mapping.items():
            cell = self._cells.get(wid)
            if not cell:
                continue
            cell.configure(bg=self._status_to_color(status))

    def set_updated_at(self, text: str) -> None:
        """Update the timestamp label shown above the matrix.

        Args:
            text: Timestamp text, usually ``HH:MM:SS``.
        """
        label = (text or "").strip() or "--:--:--"
        self._updated_var.set(f"Updated at {label}")

    # ------------------------------------------------------------------
    @staticmethod
    def _status_to_color(status: str) -> str:
        """Map status token to cell background color.

        Args:
            status: Status token (for example ``Running`` or ``Error``).
        """
        return ChannelActivityView._STATUS_COLORS.get(status, "white")


if __name__ == "__main__":
    root = tk.Tk()
    v = ChannelActivityView(root, boxes=("A","B","C","D"))
    v.pack(fill="both", expand=True)
    v.set_activity({"B11":"Running", "A2":"Error", "B10":"Done"})
    v.set_updated_at("12:03:15")
    root.mainloop()
