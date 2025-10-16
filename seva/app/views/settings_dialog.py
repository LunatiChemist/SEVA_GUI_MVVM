"""
SettingsDialog – updated
------------------------
Tkinter Toplevel dialog for editing connection and runtime settings.
Pure View: UI-only, no domain logic.

Updates:
- Close behavior improved: WM_DELETE_WINDOW triggers same as Close button.
- Relay section (IP/Port + Test button) added.
- Save button disabled until VM enables it (validation ok).
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, Optional

BoxId = str

class SettingsDialog(tk.Toplevel):
    """Modal dialog to edit app settings (UI-only)."""

    # Callback type aliases
    OnBox = Optional[Callable[[BoxId], None]]
    OnVoid = Optional[Callable[[], None]]
    OnSave = Optional[Callable[[dict], None]]

    def __init__(
        self,
        parent: tk.Widget,
        *,
        boxes: tuple[BoxId, ...] = ("A", "B", "C", "D"),
        on_test_connection: OnBox = None,
        on_test_relay: OnVoid = None,
        on_browse_results_dir: OnVoid = None,
        on_save: OnSave = None,
        on_close: OnVoid = None,
    ) -> None:
        super().__init__(parent)
        self.title("Settings")
        self.transient(parent)
        self.resizable(False, False)

        self._boxes = boxes
        self._on_test_connection = on_test_connection
        self._on_test_relay = on_test_relay
        self._on_browse_results_dir = on_browse_results_dir
        self._on_save = on_save
        self._on_close = on_close

        # Close actions
        self.protocol("WM_DELETE_WINDOW", self._on_close_clicked)

        # Data vars
        self.url_vars: Dict[BoxId, tk.StringVar] = {b: tk.StringVar(value="") for b in boxes}
        self.key_vars: Dict[BoxId, tk.StringVar] = {b: tk.StringVar(value="") for b in boxes}
        self.request_timeout_var = tk.StringVar(value="10")
        self.download_timeout_var = tk.StringVar(value="60")
        self.poll_interval_var = tk.StringVar(value="750")
        self.results_dir_var = tk.StringVar(value=".")
        self.experiment_name_var = tk.StringVar(value="")
        self.subdir_var = tk.StringVar(value="")
        self.use_streaming_var = tk.BooleanVar(value=False)
        self.debug_logging_var = tk.BooleanVar(value=False)
        self.relay_ip_var = tk.StringVar(value="")
        self.relay_port_var = tk.StringVar(value="")

        self._build_ui()

        # Center relative to parent
        self.update_idletasks()
        self.geometry(self._center_over_parent(parent))

        # Make modal
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = dict(padx=8, pady=6)

        # Connection group
        conn = ttk.Labelframe(self, text="Boxes")
        conn.grid(row=0, column=0, sticky="ew", **pad)
        conn.columnconfigure(1, weight=1)
        for row, b in enumerate(self._boxes):
            ttk.Label(conn, text=f"Box {b} URL:").grid(row=row, column=0, sticky="w")
            ttk.Entry(conn, textvariable=self.url_vars[b], width=40).grid(row=row, column=1, sticky="ew", padx=(0,8))
            ttk.Label(conn, text="API Key:").grid(row=row, column=2, sticky="e")
            ttk.Entry(conn, textvariable=self.key_vars[b], width=24, show="•").grid(row=row, column=3, sticky="w")
            ttk.Button(conn, text="Test", width=6, command=lambda bid=b: self._safe_box(self._on_test_connection, bid)).grid(row=row, column=4, sticky="w")

        # Relay group
        relay = ttk.Labelframe(self, text="Relay Box")
        relay.grid(row=1, column=0, sticky="ew", **pad)
        relay.columnconfigure(1, weight=1)
        ttk.Label(relay, text="IP").grid(row=0, column=0, sticky="w")
        ttk.Entry(relay, textvariable=self.relay_ip_var, width=20).grid(row=0, column=1, sticky="w", padx=(0,8))
        ttk.Label(relay, text="Port").grid(row=0, column=2, sticky="e")
        ttk.Entry(relay, textvariable=self.relay_port_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Button(relay, text="Test Relay", width=10, command=lambda: self._safe(self._on_test_relay)).grid(row=0, column=4, padx=(8,0))

        # Timing group
        timing = ttk.Labelframe(self, text="Timing")
        timing.grid(row=2, column=0, sticky="ew", **pad)
        ttk.Label(timing, text="Request timeout (s)").grid(row=0, column=0, sticky="w")
        ttk.Entry(timing, textvariable=self.request_timeout_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(timing, text="Download timeout (s)").grid(row=0, column=2, sticky="w", padx=(12,0))
        ttk.Entry(timing, textvariable=self.download_timeout_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(timing, text="Poll interval (ms)").grid(row=0, column=4, sticky="w", padx=(12,0))
        ttk.Entry(timing, textvariable=self.poll_interval_var, width=8).grid(row=0, column=5, sticky="w")

        # Storage group
        storage = ttk.Labelframe(self, text="Storage")
        storage.grid(row=3, column=0, sticky="ew", **pad)
        storage.columnconfigure(1, weight=1)
        ttk.Label(storage, text="Results directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(storage, textvariable=self.results_dir_var).grid(row=0, column=1, sticky="ew", padx=(0,8))
        ttk.Button(storage, text="Browse", command=lambda: self._safe(self._on_browse_results_dir)).grid(row=0, column=2, sticky="w")
        ttk.Label(storage, text="Experiment name").grid(row=1, column=0, sticky="w", pady=(4,0))
        ttk.Entry(storage, textvariable=self.experiment_name_var).grid(row=1, column=1, sticky="ew", padx=(0,8), pady=(4,0))
        ttk.Label(storage, text="Optional subdirectory").grid(row=2, column=0, sticky="w")
        ttk.Entry(storage, textvariable=self.subdir_var).grid(row=2, column=1, sticky="ew", padx=(0,8))
        ttk.Label(storage, text="Paths are generated on the Box").grid(row=3, column=0, columnspan=3, sticky="w", pady=(2,0))

        # Streaming flag
        flags = ttk.Frame(self)
        flags.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Checkbutton(flags, text="Use streaming (SSE/WebSocket)", variable=self.use_streaming_var).pack(side="left")
        ttk.Checkbutton(flags, text="Enable debug logging", variable=self.debug_logging_var).pack(side="left", padx=(12, 0))

        # Footer buttons
        footer = ttk.Frame(self)
        footer.grid(row=5, column=0, sticky="ew", **pad)
        footer.columnconfigure(0, weight=1)
        self._btn_save = ttk.Button(footer, text="Save", command=self._emit_save)
        self._btn_save.pack(side="right", padx=(0,6))
        ttk.Button(footer, text="Close", command=self._on_close_clicked).pack(side="right")

    # ------------------------------------------------------------------
    def _emit_save(self) -> None:
        settings = {
            "box_urls": {b: self.url_vars[b].get().strip() for b in self._boxes},
            "api_keys": {b: self.key_vars[b].get() for b in self._boxes},
            "timeouts": {
                "request_s": self._parse_int(self.request_timeout_var.get(), 10),
            "download_s": self._parse_int(self.download_timeout_var.get(), 60),
        },
        "poll_interval_ms": self._parse_int(self.poll_interval_var.get(), 750),
        "results_dir": self.results_dir_var.get().strip() or ".",
        "experiment_name": self.experiment_name_var.get().strip(),
        "subdir": self.subdir_var.get().strip(),
        "use_streaming": bool(self.use_streaming_var.get()),
        "debug_logging": bool(self.debug_logging_var.get()),
        "relay": {
            "ip": self.relay_ip_var.get().strip(),
            "port": self._parse_int(self.relay_port_var.get(), 0),
            },
        }
        if self._on_save:
            try:
                self._on_save(settings)
            except Exception as e:
                print(f"SettingsDialog on_save failed: {e}")

    def _on_close_clicked(self) -> None:
        self._safe(self._on_close)
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Public setters to initialize dialog fields from VM
    # ------------------------------------------------------------------
    def set_box_urls(self, mapping: Dict[BoxId, str]) -> None:
        for b, url in mapping.items():
            if b in self.url_vars:
                self.url_vars[b].set(url)

    def set_api_keys(self, mapping: Dict[BoxId, str]) -> None:
        for b, key in mapping.items():
            if b in self.key_vars:
                self.key_vars[b].set(key)

    def set_timeouts(self, request_s: int, download_s: int) -> None:
        self.request_timeout_var.set(str(request_s))
        self.download_timeout_var.set(str(download_s))

    def set_poll_interval(self, ms: int) -> None:
        self.poll_interval_var.set(str(ms))

    def set_results_dir(self, path: str) -> None:
        self.results_dir_var.set(path)

    def set_experiment_name(self, name: str) -> None:
        self.experiment_name_var.set(name)

    def set_subdir(self, value: str) -> None:
        self.subdir_var.set(value)

    def set_use_streaming(self, enabled: bool) -> None:
        self.use_streaming_var.set(bool(enabled))

    def set_debug_logging(self, enabled: bool) -> None:
        self.debug_logging_var.set(bool(enabled))

    def set_relay_config(self, ip: str, port: int) -> None:
        self.relay_ip_var.set(ip)
        self.relay_port_var.set(str(port))

    def set_save_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self._btn_save.configure(state=state)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_int(text: str, default: int) -> int:
        try:
            return int(text)
        except Exception:
            return default

    @staticmethod
    def _center_over_parent(parent: tk.Widget) -> str:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            self_w = 700
            self_h = 480
            x = px + (pw - self_w) // 2
            y = py + (ph - self_h) // 2
            return f"{self_w}x{self_h}+{x}+{y}"
        except Exception:
            return "700x480"

    def _safe(self, fn: OnVoid) -> None:
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"SettingsDialog callback failed: {e}")

    def _safe_box(self, fn: OnBox, box_id: BoxId) -> None:
        if fn:
            try:
                fn(box_id)
            except Exception as e:
                print(f"SettingsDialog test connection failed for {box_id}: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    dlg = SettingsDialog(root)
    dlg.mainloop()
