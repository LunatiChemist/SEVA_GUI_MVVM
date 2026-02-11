"""Runs-panel view for registry-backed run-group summaries.

The panel renders rows and emits open/cancel/delete/select callbacks to the app
presenter layer.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional


class RunsPanelView(ttk.Frame):
    """
    Simple table summarising run groups with actions to open folders,
    cancel groups, or remove completed entries.
    """

    def __init__(self, parent, **kwargs):
        """Build toolbar + runs table.

        Args:
            parent: Notebook parent widget.
            **kwargs: Additional frame options forwarded to ``ttk.Frame``.
        """
        super().__init__(parent, **kwargs)

        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

        self.btn_open = ttk.Button(toolbar, text="Open Folder", command=self._on_open_click, state="disabled")
        self.btn_cancel = ttk.Button(toolbar, text="Cancel", command=self._on_cancel_click, state="disabled")
        self.btn_delete = ttk.Button(toolbar, text="Delete", command=self._on_delete_click, state="disabled")
        self.btn_open.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_cancel.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_delete.pack(side=tk.LEFT)

        columns = (
            "group_id",
            "name",
            "status",
            "progress",
            "boxes",
            "started_at",
            "download_path",
        )
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        for column, width in (
            ("group_id", 180),
            ("name", 180),
            ("status", 140),
            ("progress", 90),
            ("boxes", 100),
            ("started_at", 140),
            ("download_path", 260),
        ):
            self.tree.heading(column, text=column.replace("_", " ").title())
            stretchable = column in {"name", "download_path"}
            self.tree.column(column, width=width, anchor=tk.W, stretch=stretchable)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.on_open: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[str], None]] = None
        self.on_delete: Optional[Callable[[str], None]] = None
        self.on_select: Optional[Callable[[str], None]] = None

        self.tree.bind("<<TreeviewSelect>>", self._on_select_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_rows(self, rows: List) -> None:
        """Replace table rows with registry-derived run summaries.

        Args:
            rows: Sequence of row DTOs from ``RunsVM.rows()``.
        """
        selected = self.selected_group_id()
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "",
                tk.END,
                iid=row.group_id,
                values=(
                    row.group_id,
                    row.name,
                    row.status,
                    row.progress,
                    row.boxes,
                    row.started_at,
                    row.download_path or "",
                ),
            )
        if selected and selected in self.tree.get_children(""):
            self.tree.selection_set(selected)
        self._update_buttons_state()

    def selected_group_id(self) -> Optional[str]:
        """Return currently selected group id, if any."""
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    def select_group(self, group_id: Optional[str]) -> None:
        """Programmatically select a group row if available.

        Args:
            group_id: Group id to select, or ``None`` to clear selection.
        """
        for item in self.tree.selection():
            self.tree.selection_remove(item)
        if not group_id:
            self._update_buttons_state()
            return
        if group_id in self.tree.get_children(""):
            self.tree.selection_set(group_id)
            self.tree.see(group_id)
        self._update_buttons_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_select_changed(self, _event=None) -> None:
        """Forward selection changes to external callback and update buttons.

        Args:
            _event: Tk selection-changed event.
        """
        group_id = self.selected_group_id()
        self._update_buttons_state()
        if group_id and self.on_select:
            self.on_select(group_id)

    def _update_buttons_state(self) -> None:
        """Enable action buttons only when a row is selected."""
        has_selection = self.selected_group_id() is not None
        state = "normal" if has_selection else "disabled"
        for button in (self.btn_open, self.btn_cancel, self.btn_delete):
            button.configure(state=state)

    def _on_open_click(self) -> None:
        """Emit open callback for current selection."""
        group_id = self.selected_group_id()
        if group_id and self.on_open:
            self.on_open(group_id)

    def _on_cancel_click(self) -> None:
        """Emit cancel callback for current selection."""
        group_id = self.selected_group_id()
        if group_id and self.on_cancel:
            self.on_cancel(group_id)

    def _on_delete_click(self) -> None:
        """Emit delete callback for current selection."""
        group_id = self.selected_group_id()
        if group_id and self.on_delete:
            self.on_delete(group_id)


__all__ = ["RunsPanelView"]


if __name__ == "__main__":
    from dataclasses import dataclass

    @dataclass
    class _DemoRunRow:
        group_id: str
        name: str
        status: str
        progress: str
        boxes: str
        started_at: str
        download_path: str

    root = tk.Tk()
    root.title("RunsPanelView Demo")
    root.geometry("1180x420")

    panel = RunsPanelView(root)
    panel.pack(fill="both", expand=True)

    panel.on_open = lambda gid: print(f"[demo] open folder for {gid}")
    panel.on_cancel = lambda gid: print(f"[demo] cancel requested for {gid}")
    panel.on_delete = lambda gid: print(f"[demo] delete requested for {gid}")
    panel.on_select = lambda gid: print(f"[demo] selected {gid}")

    panel.set_rows(
        [
            _DemoRunRow(
                group_id="LDP-001-TestCompliance-20260210-091410-Z8OR",
                name="LDP-001",
                status="Running",
                progress="62%",
                boxes="A,B,D",
                started_at="2026-02-10 09:14",
                download_path="",
            ),
            _DemoRunRow(
                group_id="LDP-001-TestCapacitance-20260210-091514-EFPO",
                name="LDP-001",
                status="Cancelled",
                progress="58%",
                boxes="C,D",
                started_at="2026-02-10 09:15",
                download_path="",
            ),
            _DemoRunRow(
                group_id="LDP-002-TestCapacitance-20260210-110554-F3D0",
                name="LDP-002",
                status="Done (Downloaded)",
                progress="100%",
                boxes="C,D",
                started_at="2026-02-08 11:05",
                download_path=r"C:\Users\User\Downloads\LDP\LDP-002\2026-02-08_11-05-54",
            ),
        ]
    )
    panel.select_group("rg-2026-02-10-001")

    root.mainloop()
