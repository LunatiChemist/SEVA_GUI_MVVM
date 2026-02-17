"""Modal progress view for long-running remote package updates."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Sequence, Tuple


RowTuple = Tuple[str, str, str, str, str]


class UpdateProgressDialog(tk.Toplevel):
    """Strict modal dialog showing server-authoritative update status."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.title("Remote Update Running")
        self.transient(parent)
        self.resizable(True, True)
        self.minsize(760, 360)
        self.protocol("WM_DELETE_WINDOW", self._on_close_requested)
        self._allow_close = False

        self._spinner_frames = ("|", "/", "-", "\\")
        self._spinner_index = 0
        self._spinner_after_id: str | None = None

        self._summary_var = tk.StringVar(value="Update running. Please wait.")
        self._step_var = tk.StringVar(value="Queued")
        self._heartbeat_var = tk.StringVar(value="Heartbeat: -")
        self._liveness_var = tk.StringVar(
            value="Heartbeat updates confirm the process is still running."
        )

        self._build_ui()
        self.update_idletasks()
        self.geometry(self._center_over_parent(parent))
        self.grab_set()
        self.focus_set()
        self.start_spinner()

    def _build_ui(self) -> None:
        pad = dict(padx=8, pady=6)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", **pad)
        header.columnconfigure(1, weight=1)
        self._spinner_label = ttk.Label(header, text=self._spinner_frames[0], width=2)
        self._spinner_label.grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            textvariable=self._summary_var,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(header, textvariable=self._step_var).grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Label(header, textvariable=self._heartbeat_var).grid(row=2, column=1, sticky="w", pady=(2, 0))
        ttk.Label(header, textvariable=self._liveness_var).grid(row=3, column=1, sticky="w", pady=(2, 0))

        cols = ("box", "status", "step", "message", "heartbeat")
        table_frame = ttk.Frame(self)
        table_frame.grid(row=2, column=0, sticky="nsew", **pad)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self._table = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        self._table.heading("box", text="Box")
        self._table.heading("status", text="Status")
        self._table.heading("step", text="Step")
        self._table.heading("message", text="Message")
        self._table.heading("heartbeat", text="Heartbeat")
        self._table.column("box", width=80, anchor="center")
        self._table.column("status", width=120, anchor="center")
        self._table.column("step", width=180, anchor="w")
        self._table.column("message", width=260, anchor="w")
        self._table.column("heartbeat", width=140, anchor="center")
        self._table.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._table.configure(yscrollcommand=scroll.set)

        footer = ttk.Frame(self)
        footer.grid(row=3, column=0, sticky="ew", **pad)
        footer.columnconfigure(0, weight=1)
        self._close_button = ttk.Button(
            footer,
            text="Close",
            command=self._close_now,
            state=tk.DISABLED,
        )
        self._close_button.grid(row=0, column=1, sticky="e")

    def set_overview(self, *, summary: str, step: str, heartbeat_text: str, liveness: str) -> None:
        """Update top-level labels from polling controller state."""
        self._summary_var.set(summary)
        self._step_var.set(f"Current step: {step or '-'}")
        self._heartbeat_var.set(f"Heartbeat: {heartbeat_text or '-'}")
        self._liveness_var.set(liveness)

    def set_rows(self, rows: Iterable[Sequence[str]]) -> None:
        """Replace table rows with latest per-box status snapshot."""
        for item in self._table.get_children():
            self._table.delete(item)
        for row in rows:
            values = tuple(row)
            if len(values) != 5:
                continue
            self._table.insert("", "end", values=values)

    def mark_terminal(self, *, summary: str, allow_close: bool = True) -> None:
        """Switch dialog into terminal mode and optionally allow closing."""
        self._summary_var.set(summary)
        self.stop_spinner()
        if allow_close:
            self._allow_close = True
            self._close_button.configure(state=tk.NORMAL)

    def start_spinner(self) -> None:
        """Start spinner animation loop."""
        self.stop_spinner()
        self._tick_spinner()

    def stop_spinner(self) -> None:
        """Stop spinner animation loop."""
        if self._spinner_after_id:
            try:
                self.after_cancel(self._spinner_after_id)
            except Exception:
                pass
            self._spinner_after_id = None

    def _tick_spinner(self) -> None:
        self._spinner_label.configure(text=self._spinner_frames[self._spinner_index])
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        self._spinner_after_id = self.after(220, self._tick_spinner)

    def _on_close_requested(self) -> None:
        if self._allow_close:
            self._close_now()

    def _close_now(self) -> None:
        self.stop_spinner()
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    @staticmethod
    def _center_over_parent(parent: tk.Widget) -> str:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            width = 860
            height = 440
            x = px + (pw - width) // 2
            y = py + (ph - height) // 2
            return f"{width}x{height}+{x}+{y}"
        except Exception:
            return "860x440"


__all__ = ["UpdateProgressDialog", "RowTuple"]

