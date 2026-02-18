"""Dialog view for presenting discovered device rows."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Mapping, Optional


class DiscoveryResultsDialog(tk.Toplevel):
    """Simple modal dialog that shows a table of discovered devices."""

    def __init__(
        self,
        master,
        rows: Iterable[Mapping],
        title: str = "Discovered Devices",
        on_close: Optional[callable] = None,
    ):
        super().__init__(master)
        self.title(title)
        self.on_close = on_close
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        cols = ("name", "ip", "port", "health_url", "properties")
        headings = {
            "name": "Name",
            "ip": "IPv4",
            "port": "Port",
            "health_url": "Health URL",
            "properties": "Properties",
        }
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for key in cols:
            self.tree.heading(key, text=headings[key])
            width = 260 if key in {"health_url", "properties"} else 120
            self.tree.column(key, width=width, anchor="w")

        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        ttk.Button(self, text="Close", command=self._on_close).grid(
            row=1, column=0, columnspan=2, pady=8
        )

        self._populate(rows)

        self.transient(master)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()
        self._center_over_master()

    def _populate(self, rows: Iterable[Mapping]) -> None:
        self.tree.delete(*self.tree.get_children())
        any_rows = False
        for item in rows:
            any_rows = True
            properties = item.get("properties", {}) or {}
            properties_text = ", ".join(f"{k}={v}" for k, v in properties.items())
            self.tree.insert(
                "",
                "end",
                values=(
                    str(item.get("name", "") or ""),
                    str(item.get("ip", "") or ""),
                    str(item.get("port", "") or ""),
                    str(item.get("health_url", "") or ""),
                    properties_text,
                ),
            )
        if not any_rows:
            self.tree.insert("", "end", values=("—", "—", "—", "—", "—"))

    def _center_over_master(self):
        try:
            self.update_idletasks()
            if self.master and self.master.winfo_ismapped():
                mx, my = self.master.winfo_rootx(), self.master.winfo_rooty()
                mw, mh = self.master.winfo_width(), self.master.winfo_height()
                w, h = self.winfo_width(), self.winfo_height()
                x = mx + (mw - w) // 2
                y = my + (mh - h) // 3
            else:
                w, h = self.winfo_width(), self.winfo_height()
                x = (self.winfo_screenwidth() - w) // 2
                y = (self.winfo_screenheight() - h) // 3
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        if callable(self.on_close):
            try:
                self.on_close()
            except Exception:
                pass
        self.destroy()
