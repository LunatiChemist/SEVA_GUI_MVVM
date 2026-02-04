"""Dialog view for presenting discovered device rows.

The dialog is UI-only and displays discovery payloads produced by use-case and
controller layers.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Iterable, Mapping, Optional

class DiscoveryResultsDialog(tk.Toplevel):
    """
    Simple modal dialog that shows a table of discovered SEVA devices.
    Expects an iterable of mappings with keys:
      base_url, box_id, devices, api_version, build
    """
    def __init__(self, master, rows: Iterable[Mapping], title: str = "Discovered Devices",
                 on_close: Optional[callable] = None):
        super().__init__(master)
        self.title(title)
        self.on_close = on_close
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # --- Treeview
        cols = ("base_url", "box_id", "devices", "api_version", "build")
        headings = {
            "base_url": "Base URL",
            "box_id": "Box ID",
            "devices": "Devices",
            "api_version": "API",
            "build": "Build",
        }
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for key in cols:
            self.tree.heading(key, text=headings[key])
            # Heuristic widths - the user can resize columns later
            width = 200 if key == "base_url" else 100
            self.tree.column(key, width=width, anchor="w")
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        # --- Buttons
        btn = ttk.Button(self, text="Close", command=self._on_close)
        btn.grid(row=1, column=0, columnspan=2, pady=8)

        # --- Populate
        self._populate(rows)

        # --- Modal
        self.transient(master)
        try:
            self.grab_set()
        except tk.TclError:
            pass  # if another grab is already active
        self.focus_set()

        # gently center over the parent window
        self._center_over_master()

    def _populate(self, rows: Iterable[Mapping]) -> None:
        self.tree.delete(*self.tree.get_children())
        any_rows = False
        for item in rows:
            any_rows = True
            base_url = str(item.get("base_url", "")).strip()
            box_id = item.get("box_id", "") or ""
            devices = item.get("devices", "")
            api_version = item.get("api_version", "") or ""
            build = item.get("build", "") or ""
            self.tree.insert("", "end", values=(base_url, box_id, devices, api_version, build))
        if not any_rows:
            # Placeholder row so the user sees that nothing was found
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
            self.geometry(f"+{max(0,x)}+{max(0,y)}")
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

demo_rows = [
        {
            "base_url": "http://192.168.1.10",
            "box_id": "SEVA-001",
            "devices": ["thermostat", "sensor-1"],
            "api_version": "v1.2.0",
            "build": "2025-10-10",
        },
        {
            "base_url": "http://192.168.1.11",
            "box_id": "SEVA-002",
            "devices": ["light", "sensor-2"],
            "api_version": "v1.1.5",
            "build": "2025-09-22",
        },
        # An entry with missing fields (test how your dialog handles it)
        {
            "base_url": "http://10.0.0.5",
            "devices": [],
        },
        # You can also pass an empty list to see the placeholder row:
        # {}
    ]

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Demo: DiscoveryResultsDialog")
    root.geometry("400x120")

    def open_demo_dialog():
        # Open dialog modally - on_close callback removes nothing special in this demo
        DiscoveryResultsDialog(root, demo_rows, title="Discovered SEVA Devices")

    # Simple GUI with a button to open the dialog
    frame = ttk.Frame(root, padding=12)
    frame.pack(expand=True, fill="both")

    lbl = ttk.Label(frame, text="Click 'Show results' to show the demo.")
    lbl.pack(pady=(0, 8))

    btn = ttk.Button(frame, text="Show results", command=open_demo_dialog)
    btn.pack()

    # Optional: open dialog directly on start
    # open_demo_dialog()

    root.mainloop()