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
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    def select_group(self, group_id: Optional[str]) -> None:
        """Programmatically select a group row if available."""
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
        group_id = self.selected_group_id()
        self._update_buttons_state()
        if group_id and self.on_select:
            self.on_select(group_id)

    def _update_buttons_state(self) -> None:
        has_selection = self.selected_group_id() is not None
        state = "normal" if has_selection else "disabled"
        for button in (self.btn_open, self.btn_cancel, self.btn_delete):
            button.configure(state=state)

    def _on_open_click(self) -> None:
        group_id = self.selected_group_id()
        if group_id and self.on_open:
            self.on_open(group_id)

    def _on_cancel_click(self) -> None:
        group_id = self.selected_group_id()
        if group_id and self.on_cancel:
            self.on_cancel(group_id)

    def _on_delete_click(self) -> None:
        group_id = self.selected_group_id()
        if group_id and self.on_delete:
            self.on_delete(group_id)


__all__ = ["RunsPanelView"]
