"""
WellGridView
------------
Grid of wells grouped by boxes (A–D). Pure View (no backend logic).

Update:
- The grid no longer reflects run statuses (Queued/Running/...). Those live in
  ChannelActivity. Here we only show selection and a "configured" indicator.
- "Configured" wells are colored green. After submit they are reset to default.

Public API for ViewModel:
- set_boxes(iterable[str])
- set_selection(iterable[str])
- get_selection() -> set[str]
- set_configured_wells(iterable[str])      # replace configured set
- add_configured_wells(iterable[str])      # mark as configured (green)
- clear_configured_wells(iterable[str])    # remove configured state for given wells
- clear_all_configured()                   # reset all to default (e.g., after submit)
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Iterable, Optional, Sequence, Set


WellId = str
BoxId = str


class WellGridView(ttk.Frame):
    """Grid of wells grouped by boxes (A–D)."""

    # Callback types
    OnSelect = Optional[Callable[[Set[WellId]], None]]
    OnVoid = Optional[Callable[[], None]]
    OnWell = Optional[Callable[[WellId], None]]

    def __init__(
        self,
        parent: tk.Widget,
        *,
        boxes: Sequence[BoxId] = ("A", "B", "C", "D"),
        wells_per_box: int = 10,
        on_select_wells: OnSelect = None,
        on_toggle_enable_selected: OnVoid = None,
        on_copy_params_from: OnWell = None,
        on_paste_params_to_selection: OnVoid = None,
        on_reset_selected: OnVoid = None,
        on_open_plot: OnWell = None,
    ) -> None:
        super().__init__(parent)

        self._boxes = list(boxes)
        self._wells_per_box = int(wells_per_box)
        self._on_select_wells = on_select_wells
        self._on_toggle_enable_selected = on_toggle_enable_selected
        self._on_copy_params_from = on_copy_params_from
        self._on_paste_params_to_selection = on_paste_params_to_selection
        self._on_reset_selected = on_reset_selected
        self._on_open_plot = on_open_plot

        # State
        self._buttons: Dict[WellId, tk.Button] = {}
        self._selected: Set[WellId] = set()
        self._configured: Set[WellId] = set()  # wells with assigned params

        self._build_ui()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(
            toolbar,
            text="Reset Well Config",
            command=self._on_reset_selected,
        ).pack(side="left")

        grid = ttk.Frame(self)
        grid.pack(fill="both", expand=True)

        global_index = 1
        for col, box in enumerate(self._boxes):
            lf = ttk.Labelframe(grid, text=f"{box}")
            lf.grid(row=0, column=col, padx=8, pady=6, sticky="n")
            for i in range(1, self._wells_per_box + 1):
                r = (i - 1) % 5
                c = 0 if i <= 5 else 1
                wid = f"{box}{global_index}"
                btn = tk.Button(
                    lf,
                    text=str(global_index),
                    width=6,
                    height=2,
                    relief="groove",
                    bg=self._color_default(),
                )
                btn.grid(row=r, column=c, padx=3, pady=2, sticky="nsew")
                btn.bind("<Button-1>", lambda e, w=wid: self._on_click(e, w))
                btn.bind("<Double-Button-1>", lambda e, w=wid: self._on_open_plot(w))
                btn.bind("<Button-3>", lambda e, w=wid: self._context_menu(e, w))
                self._buttons[wid] = btn
                global_index += 1

    # ------------------------------------------------------------------
    # Public API used by ViewModel
    # ------------------------------------------------------------------
    def set_boxes(self, boxes: Iterable[BoxId]) -> None:
        """Rebuild grid for a new set of boxes."""
        self._boxes = list(boxes)
        for child in list(self.winfo_children()):
            child.destroy()
        self._buttons.clear()
        self._selected.clear()
        self._configured.clear()
        self._build_ui()
        self._emit_selection()

    def set_configured_wells(self, wells: Iterable[WellId]) -> None:
        """Replace the configured set and recolor buttons (green)."""
        self._configured = set(wells)
        self._repaint_all()

    def add_configured_wells(self, wells: Iterable[WellId]) -> None:
        self._configured.update(wells)
        self._repaint_some(wells)

    def clear_configured_wells(self, wells: Iterable[WellId]) -> None:
        for w in wells:
            self._configured.discard(w)
        self._repaint_some(wells)

    def clear_all_configured(self) -> None:
        self._configured.clear()
        self._repaint_all()

    def get_selection(self) -> Set[WellId]:
        return set(self._selected)

    def set_selection(self, wells: Iterable[WellId]) -> None:
        self._selected = set(wells)
        self._repaint_all()
        self._emit_selection()

    # ------------------------------------------------------------------
    # Coloring rules (no run statuses here)
    # ------------------------------------------------------------------
    def _color_default(self) -> str:
        return "white"  # default idle/empty

    def _color_selected(self) -> str:
        return "#bbdefb"  # light blue

    def _color_configured(self) -> str:
        return "#c8e6c9"  # light green

    def _apply_style(self, wid: WellId) -> None:
        btn = self._buttons.get(wid)
        if not btn:
            return
        if wid in self._selected:
            btn.configure(bg=self._color_selected())
        elif wid in self._configured:
            btn.configure(bg=self._color_configured())
        else:
            btn.configure(bg=self._color_default())

    # ------------------------------------------------------------------
    # Selection & helpers
    # ------------------------------------------------------------------
    def _on_click(self, event: tk.Event, well_id: str) -> None:
        shift = bool(event.state & 0x0001)  # ShiftMask
        if shift:
            if well_id in self._selected:
                self._selected.remove(well_id)
            else:
                self._selected.add(well_id)
        else:
            self._selected = {well_id}
        self._repaint_all()
        self._emit_selection()
    
    def _toggle_select(self, well_id: WellId) -> None:
        if well_id in self._selected:
            self._selected.remove(well_id)
        else:
            self._selected.add(well_id)
        self._apply_style(well_id)
        self._emit_selection()

    def _repaint_some(self, wells: Iterable[WellId]) -> None:
        for w in wells:
            self._apply_style(w)

    def _repaint_all(self) -> None:
        for w in self._buttons.keys():
            self._apply_style(w)

    def _emit_selection(self) -> None:
        if self._on_select_wells:
            self._on_select_wells(set(self._selected))

    def _context_menu(self, event: tk.Event, well_id: WellId) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Copy Params from", command=lambda: self._on_copy_params_from(well_id))
        menu.add_command(label="Paste Params to Selection", command=self._on_paste_params_to_selection)
        menu.add_separator()
        menu.add_command(label="Enable/Disable Selection", command=self._on_toggle_enable_selected)
        menu.add_command(label="Reset Selection", command=self._on_reset_selected)
        menu.add_separator()
        menu.add_command(label="Open PNG", command=lambda: self._on_open_plot(well_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    grid = WellGridView(root, boxes=("A", "B", "C","D","E","F"))
    grid.pack(fill="both", expand=True)
    root.mainloop()
