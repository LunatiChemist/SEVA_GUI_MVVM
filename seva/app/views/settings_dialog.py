"""Settings dialog view for editing runtime configuration.

This UI component exposes callback hooks for save/test/discovery actions and
contains no persistence or network logic of its own.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from seva.app.views.theme import apply_modern_theme
from typing import Callable, Dict, Optional


BoxId = str


class SettingsDialog(tk.Toplevel):
    """Modal dialog to edit app settings (UI-only)."""

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
        on_browse_firmware: OnVoid = None,
        on_discover_devices: OnVoid = None,
        on_open_nas_setup: OnVoid = None,
        on_save: OnSave = None,
        on_flash_firmware: OnVoid = None,
        on_close: OnVoid = None,
    ) -> None:
        """Initialize modal settings dialog and field variables.

        Args:
            parent: Root window used for modality and centering.
            boxes: Ordered box ids rendered in connection rows.
            on_test_connection: Per-box callback for connection tests.
            on_test_relay: Callback for relay connection test.
            on_browse_results_dir: Callback for selecting local results dir.
            on_browse_firmware: Callback for selecting firmware image.
            on_discover_devices: Callback that runs discovery workflow.
            on_open_nas_setup: Callback opening NAS setup flow.
            on_save: Callback receiving a normalized settings payload dict.
            on_flash_firmware: Callback triggering firmware flashing flow.
            on_close: Callback invoked when dialog closes.
        """
        super().__init__(parent)
        apply_modern_theme(self)
        self.title("Settings")
        self.transient(parent)
        self.resizable(False, False)

        self._boxes = boxes
        self._on_test_connection = on_test_connection
        self._on_test_relay = on_test_relay
        self._on_browse_results_dir = on_browse_results_dir
        self._on_browse_firmware = on_browse_firmware
        self._on_discover_devices = on_discover_devices
        self._on_open_nas_setup = on_open_nas_setup
        self._on_save = on_save
        self._on_flash_firmware = on_flash_firmware
        self._on_close = on_close

        self.protocol("WM_DELETE_WINDOW", self._on_close_clicked)

        self.url_vars: Dict[BoxId, tk.StringVar] = {box: tk.StringVar(value="") for box in boxes}
        self.key_vars: Dict[BoxId, tk.StringVar] = {box: tk.StringVar(value="") for box in boxes}
        self.request_timeout_var = tk.StringVar(value="10")
        self.download_timeout_var = tk.StringVar(value="60")
        self.poll_interval_var = tk.StringVar(value="750")
        self.poll_backoff_var = tk.StringVar(value="5000")
        self.results_dir_var = tk.StringVar(value=".")
        self.experiment_name_var = tk.StringVar(value="")
        self.subdir_var = tk.StringVar(value="")
        self.auto_download_var = tk.BooleanVar(value=True)
        self.use_streaming_var = tk.BooleanVar(value=False)
        self.debug_logging_var = tk.BooleanVar(value=False)
        self.relay_ip_var = tk.StringVar(value="")
        self.relay_port_var = tk.StringVar(value="0")
        self.firmware_path_var = tk.StringVar(value="")

        self._build_ui()

        self.update_idletasks()
        self.geometry(self._center_over_parent(parent))
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Create all dialog widget groups and footer actions."""
        pad = dict(padx=10, pady=8)

        # Connection group
        connection = ttk.Labelframe(self, text="Boxes")
        connection.grid(row=0, column=0, sticky="ew", **pad)
        connection.columnconfigure(1, weight=1)
        for row, box in enumerate(self._boxes):
            ttk.Label(connection, text=f"Box {box} URL:").grid(row=row, column=0, sticky="w")
            ttk.Entry(connection, textvariable=self.url_vars[box], width=40).grid(
                row=row, column=1, sticky="ew", padx=(0, 8)
            )
            ttk.Label(connection, text="API Key:").grid(row=row, column=2, sticky="e")
            ttk.Entry(connection, textvariable=self.key_vars[box], width=24, show="*").grid(
                row=row, column=3, sticky="w"
            )
            ttk.Button(
                connection,
                text="Test",
                width=6,
                command=lambda bid=box: self._safe_box(self._on_test_connection, bid),
            ).grid(row=row, column=4, sticky="w")

        ttk.Button(
            connection,
            text="Scan Network",
            command=lambda: self._safe(self._on_discover_devices),
        ).grid(row=len(self._boxes), column=0, columnspan=5, sticky="w", pady=(8, 0))

        # Relay group
        relay = ttk.Labelframe(self, text="Relay Box")
        relay.grid(row=1, column=0, sticky="ew", **pad)
        relay.columnconfigure(1, weight=1)
        ttk.Label(relay, text="IP").grid(row=0, column=0, sticky="w")
        ttk.Entry(relay, textvariable=self.relay_ip_var, width=20).grid(
            row=0, column=1, sticky="w", padx=(0, 8)
        )
        ttk.Label(relay, text="Port").grid(row=0, column=2, sticky="e")
        ttk.Entry(relay, textvariable=self.relay_port_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Button(relay, text="Test Relay", width=10, command=lambda: self._safe(self._on_test_relay)).grid(
            row=0, column=4, padx=(8, 0)
        )

        # Timing group
        timing = ttk.Labelframe(self, text="Timing")
        timing.grid(row=2, column=0, sticky="ew", **pad)
        for col in range(4):
            timing.columnconfigure(col, weight=1 if col % 2 == 1 else 0)
        ttk.Label(timing, text="Request timeout (s)").grid(row=0, column=0, sticky="w")
        ttk.Entry(timing, textvariable=self.request_timeout_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(timing, text="Download timeout (s)").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Entry(timing, textvariable=self.download_timeout_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(timing, text="Poll interval (ms)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(timing, textvariable=self.poll_interval_var, width=8).grid(
            row=1, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Label(timing, text="Poll backoff max (ms)").grid(row=1, column=2, sticky="w", pady=(8, 0), padx=(12, 0))
        ttk.Entry(timing, textvariable=self.poll_backoff_var, width=8).grid(
            row=1, column=3, sticky="w", pady=(8, 0)
        )

        # Storage group
        storage = ttk.Labelframe(self, text="Storage")
        storage.grid(row=3, column=0, sticky="ew", **pad)
        storage.columnconfigure(1, weight=1)
        ttk.Label(storage, text="Results directory").grid(row=0, column=0, sticky="w")
        ttk.Entry(storage, textvariable=self.results_dir_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            storage,
            text="Choose Results Dir…",
            command=lambda: self._safe(self._on_browse_results_dir),
        ).grid(row=0, column=2, sticky="w")
        ttk.Label(storage, text="Experiment name").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(storage, textvariable=self.experiment_name_var).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=(6, 0)
        )
        ttk.Label(storage, text="Optional subdirectory").grid(row=2, column=0, sticky="w")
        ttk.Entry(storage, textvariable=self.subdir_var).grid(row=2, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(storage, text="Paths are generated on the Box").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

        # Firmware group
        firmware = ttk.Labelframe(self, text="Firmware")
        firmware.grid(row=4, column=0, sticky="ew", **pad)
        firmware.columnconfigure(1, weight=1)
        ttk.Label(firmware, text="Firmware image (.bin)").grid(row=0, column=0, sticky="w")
        ttk.Entry(firmware, textvariable=self.firmware_path_var).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(
            firmware,
            text="Browse…",
            command=lambda: self._safe(self._on_browse_firmware),
        ).grid(row=0, column=2, sticky="w")
        ttk.Button(
            firmware,
            text="Flash Firmware",
            command=lambda: self._safe(self._on_flash_firmware),
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # NAS group
        nas = ttk.Labelframe(self, text="NAS")
        nas.grid(row=5, column=0, sticky="ew", **pad)
        ttk.Button(
            nas,
            text="Open NAS Setup…",
            command=lambda: self._safe(self._on_open_nas_setup),
        ).pack(side="left")

        # Flags
        flags = ttk.Frame(self)
        flags.grid(row=6, column=0, sticky="ew", **pad)
        ttk.Checkbutton(
            flags,
            text="Auto-download results on completion",
            variable=self.auto_download_var,
        ).pack(side="left")
        ttk.Checkbutton(flags, text="Use streaming (SSE/WebSocket)", variable=self.use_streaming_var).pack(
            side="left", padx=(12, 0)
        )
        ttk.Checkbutton(flags, text="Enable debug logging", variable=self.debug_logging_var).pack(
            side="left", padx=(12, 0)
        )

        # Footer
        footer = ttk.Frame(self)
        footer.grid(row=7, column=0, sticky="ew", **pad)
        footer.columnconfigure(0, weight=1)
        self._btn_save = ttk.Button(footer, text="Save", style="Primary.TButton", command=self._emit_save)
        self._btn_save.pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="Close", command=self._on_close_clicked).pack(side="right")

    # ------------------------------------------------------------------
    def _emit_save(self) -> None:
        """Collect field values and emit them through ``on_save`` callback."""
        settings = {
            "api_base_urls": {box: self.url_vars[box].get().strip() for box in self._boxes},
            "api_keys": {box: self.key_vars[box].get() for box in self._boxes},
            "request_timeout_s": self._parse_int(self.request_timeout_var.get(), 10),
            "download_timeout_s": self._parse_int(self.download_timeout_var.get(), 60),
            "poll_interval_ms": self._parse_int(self.poll_interval_var.get(), 750),
            "poll_backoff_max_ms": self._parse_int(self.poll_backoff_var.get(), 5000),
            "results_dir": self.results_dir_var.get().strip() or ".",
            "auto_download_on_complete": bool(self.auto_download_var.get()),
            "experiment_name": self.experiment_name_var.get().strip(),
            "subdir": self.subdir_var.get().strip(),
            "use_streaming": bool(self.use_streaming_var.get()),
            "debug_logging": bool(self.debug_logging_var.get()),
            "relay_ip": self.relay_ip_var.get().strip(),
            "relay_port": self._parse_int(self.relay_port_var.get(), 0),
            "firmware_path": self.firmware_path_var.get().strip(),
        }
        if self._on_save:
            try:
                self._on_save(settings)
            except Exception as exc:  # pragma: no cover - GUI logging only
                print(f"SettingsDialog on_save failed: {exc}")

    def _on_close_clicked(self) -> None:
        """Invoke close callback and destroy dialog safely."""
        self._safe(self._on_close)
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Public setters to initialize dialog fields from VM
    # ------------------------------------------------------------------
    def set_api_base_urls(self, mapping: Dict[BoxId, str]) -> None:
        """Populate base URL fields from settings viewmodel state.

        Args:
            mapping: Box-id to base URL mapping.
        """
        for box, url in (mapping or {}).items():
            if box in self.url_vars:
                self.url_vars[box].set(url)

    def set_api_keys(self, mapping: Dict[BoxId, str]) -> None:
        """Populate API key fields from settings viewmodel state.

        Args:
            mapping: Box-id to API key mapping.
        """
        for box, key in (mapping or {}).items():
            if box in self.key_vars:
                self.key_vars[box].set(key)

    def set_timeouts(self, request_s: int, download_s: int) -> None:
        """Set request/download timeout inputs.

        Args:
            request_s: Request timeout in seconds.
            download_s: Download timeout in seconds.
        """
        self.request_timeout_var.set(str(request_s))
        self.download_timeout_var.set(str(download_s))

    def set_poll_interval(self, ms: int) -> None:
        """Set poll interval input.

        Args:
            ms: Poll interval in milliseconds.
        """
        self.poll_interval_var.set(str(ms))

    def set_poll_backoff_max(self, ms: int) -> None:
        """Set maximum poll backoff input.

        Args:
            ms: Maximum poll backoff in milliseconds.
        """
        self.poll_backoff_var.set(str(ms))

    def set_results_dir(self, path: str) -> None:
        """Set results directory input.

        Args:
            path: Directory path string.
        """
        self.results_dir_var.set(path)

    def set_experiment_name(self, name: str) -> None:
        """Set experiment name input.

        Args:
            name: Experiment name string.
        """
        self.experiment_name_var.set(name)

    def set_subdir(self, value: str) -> None:
        """Set optional subdirectory input.

        Args:
            value: Optional subdirectory string.
        """
        self.subdir_var.set(value)

    def set_auto_download(self, enabled: bool) -> None:
        """Set auto-download checkbox state.

        Args:
            enabled: Whether auto-download should be enabled.
        """
        self.auto_download_var.set(bool(enabled))

    def set_use_streaming(self, enabled: bool) -> None:
        """Set streaming checkbox state.

        Args:
            enabled: Whether streaming mode should be enabled.
        """
        self.use_streaming_var.set(bool(enabled))

    def set_debug_logging(self, enabled: bool) -> None:
        """Set debug logging checkbox state.

        Args:
            enabled: Whether debug logging should be enabled.
        """
        self.debug_logging_var.set(bool(enabled))

    def set_relay_config(self, ip: str, port: int) -> None:
        """Set relay endpoint inputs.

        Args:
            ip: Relay IP address.
            port: Relay TCP port.
        """
        self.relay_ip_var.set(ip)
        self.relay_port_var.set(str(port))

    def set_firmware_path(self, path: str) -> None:
        """Set firmware image path input.

        Args:
            path: Firmware image path string.
        """
        self.firmware_path_var.set(path)

    def set_save_enabled(self, enabled: bool) -> None:
        """Enable or disable the Save button.

        Args:
            enabled: Whether the Save button should be enabled.
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self._btn_save.configure(state=state)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_int(text: str, default: int) -> int:
        """Parse integer input, returning fallback on parse failure.

        Args:
            text: Input text to parse.
            default: Fallback integer value.
        """
        try:
            return int(text)
        except Exception:
            return default

    @staticmethod
    def _center_over_parent(parent: tk.Widget) -> str:
        """Return geometry string centered over parent window when possible.

        Args:
            parent: Parent widget used as centering anchor.
        """
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            width = 600
            height = 650
            x = px + (pw - width) // 2
            y = py + (ph - height) // 2
            return f"{width}x{height}+{x}+{y}"
        except Exception:
            return "600x650"

    def _safe(self, fn: OnVoid) -> None:
        """Invoke no-arg callback only when provided.

        Args:
            fn: Optional callback.
        """
        if fn:
            fn()

    def _safe_box(self, fn: OnBox, box_id: BoxId) -> None:
        """Invoke box callback only when provided.

        Args:
            fn: Optional callback taking box id.
            box_id: Box id argument for callback.
        """
        if fn:
            fn(box_id)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("SettingsDialog Demo Host")
    root.geometry("900x700")

    dialog = SettingsDialog(
        root,
        on_test_connection=lambda box: print(f"[demo] test connection for box {box}"),
        on_test_relay=lambda: print("[demo] test relay"),
        on_browse_results_dir=lambda: print("[demo] browse results dir"),
        on_browse_firmware=lambda: print("[demo] browse firmware"),
        on_discover_devices=lambda: print("[demo] discover devices"),
        on_open_nas_setup=lambda: print("[demo] open NAS setup"),
        on_save=lambda payload: print(f"[demo] save payload with {len(payload)} keys"),
        on_flash_firmware=lambda: print("[demo] flash firmware"),
        on_close=lambda: print("[demo] close dialog"),
    )

    dialog.set_api_base_urls(
        {
            "A": "http://192.168.1.10:8000/",
            "B": "http://192.168.1.18:8000/",
            "C": "http://192.168.1.98:8000/",
            "D": "http://192.168.1.75:8000/",
        }
    )
    dialog.set_api_keys(
        {
            "A": "12598",
            "B": "12598",
            "C": "12598",
            "D": "12598",
        }
    )
    dialog.set_timeouts(request_s=12, download_s=180)
    dialog.set_poll_interval(750)
    dialog.set_poll_backoff_max(5000)
    dialog.set_results_dir(r"C:\Users\User\Downloads\LDP")
    dialog.set_experiment_name("LDP-001")
    dialog.set_subdir("TestCapacitance")
    dialog.set_auto_download(True)
    dialog.set_use_streaming(True)
    dialog.set_debug_logging(False)
    dialog.set_relay_config(ip="10.0.10.40", port=502)
    dialog.set_firmware_path(r"C:\Users\User\Downloads\potentiostat_v2.3.1.bin")

    dialog.mainloop()
