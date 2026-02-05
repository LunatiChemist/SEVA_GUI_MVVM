"""Controller for settings dialog actions and persistence updates.

This module keeps settings workflow orchestration out of views by handling
dialog callbacks, validation, persistence, and side effects (adapter resets,
polling restarts, and box-configuration reapplication).
"""

from __future__ import annotations


import logging
import os
import tempfile
from typing import Callable, Optional
from tkinter import filedialog, messagebox

from seva.domain.ports import StoragePort, UseCaseError
from seva.viewmodels.settings_vm import SettingsVM
from seva.app.controller import AppController
from seva.app.nas_gui_smb import NASSetupGUI
from seva.app.views.settings_dialog import SettingsDialog


class SettingsController:
    """Settings dialog orchestration and persistence."""

    def __init__(
        self,
        *,
        win,
        settings_vm: SettingsVM,
        controller: AppController,
        storage: StoragePort,
        test_relay,
        ensure_adapter: Callable[[], bool],
        toast_error,
        on_discover_devices: Callable[[Optional[SettingsDialog]], None],
        apply_logging_preferences: Callable[[], None],
        apply_box_configuration: Callable[[], None],
        stop_all_polling: Callable[[], None],
    ) -> None:
        """Store collaborators needed by settings UI workflows.

        Args:
            win: Root window used for toasts and modal parenting.
            settings_vm: Settings viewmodel holding editable values.
            controller: App controller that owns runtime adapter wiring.
            storage: Persistence port for user settings.
            test_relay: Relay connectivity use-case callable.
            ensure_adapter: Callback ensuring adapters/use-cases are ready.
            toast_error: Callback that converts exceptions to user toasts.
            on_discover_devices: Callback launching discovery workflow.
            apply_logging_preferences: Callback applying debug log settings.
            apply_box_configuration: Callback refreshing configured box UI.
            stop_all_polling: Callback stopping active polling loops.
        """
        self._log = logging.getLogger(__name__)
        self.win = win
        self.settings_vm = settings_vm
        self.controller = controller
        self.storage = storage
        self.test_relay = test_relay
        self._ensure_adapter = ensure_adapter
        self._toast_error = toast_error
        self._on_discover_devices = on_discover_devices
        self._apply_logging_preferences = apply_logging_preferences
        self._apply_box_configuration = apply_box_configuration
        self._stop_all_polling = stop_all_polling

    def open_dialog(self) -> None:
        """Open settings dialog and wire per-button handlers."""
        dlg: Optional[SettingsDialog] = None

        def handle_test_connection(box_id: str) -> None:
            """Test API connectivity for a single box id.

            Args:
                box_id: Box identifier selected from dialog row.
            """
            if not dlg:
                return
            url_var = dlg.url_vars.get(box_id)
            if url_var is None:
                self.win.show_toast(f"Box {box_id}: not available.")
                return
            base_url = url_var.get().strip()
            if not base_url:
                self.win.show_toast(f"Box {box_id}: URL required for test.")
                return

            api_key_var = dlg.key_vars.get(box_id)
            api_key = api_key_var.get().strip() if api_key_var else ""
            request_timeout = SettingsDialog._parse_int(
                dlg.request_timeout_var.get(), self.settings_vm.request_timeout_s
            )

            adapter = self.controller.device_adapter
            if adapter is None:
                saved_url = (self.settings_vm.api_base_urls or {}).get(box_id, "").strip()
                if saved_url:
                    if self._ensure_adapter():
                        adapter = self.controller.device_adapter

            uc = self.controller.build_test_connection(
                box_id=box_id,
                base_url=base_url,
                api_key=api_key,
                request_timeout=request_timeout,
            )

            assert uc is not None
            try:
                result = uc(box_id)
            except UseCaseError as err:
                reason = err.message or str(err)
                self.win.show_toast(f"Box {box_id}: failed ({reason})")
                return
            except Exception as exc:
                self._toast_error(exc, context=f"Box {box_id}")
                return

            status = "ok" if result.get("ok") else "failed"
            devices = result.get("device_count")
            device_text = f"devices={devices}" if devices is not None else "devices=?"
            health = result.get("health") or {}
            reason = str(
                health.get("message")
                or health.get("detail")
                or health.get("error")
                or ""
            ).strip()
            detail = device_text if status == "ok" else (reason or device_text)
            self.win.show_toast(f"Box {box_id}: {status} ({detail})")

        def handle_test_relay() -> None:
            """Test relay connectivity with values from dialog fields."""
            if not dlg:
                return
            ip = dlg.relay_ip_var.get().strip()
            port_raw = dlg.relay_port_var.get().strip()
            if not ip:
                self.win.show_toast("Relay IP required for test.")
                return
            if not port_raw:
                self.win.show_toast("Relay port required for test.")
                return
            try:
                port = int(port_raw)
            except ValueError:
                self.win.show_toast("Relay port must be an integer.")
                return
            try:
                ok = self.test_relay(ip, port)
            except Exception as exc:
                self.win.show_toast(str(exc))
                return
            message = "Relay test successful." if ok else "Relay test failed."
            self.win.show_toast(message)

        def handle_browse_results_dir() -> None:
            """Open directory picker and set results directory field."""
            if not dlg:
                return
            current = dlg.results_dir_var.get().strip()
            if not current:
                current = self.settings_vm.results_dir or "."
            initial_dir = current
            if initial_dir and not os.path.isdir(initial_dir):
                home_dir = os.path.expanduser("~")
                initial_dir = home_dir if os.path.isdir(home_dir) else ""
            try:
                selected = filedialog.askdirectory(
                    parent=dlg,
                    initialdir=initial_dir or None,
                    title="Select Results Directory",
                )
            except Exception as exc:
                self.win.show_toast(f"Could not open folder picker: {exc}")
                return
            if not selected:
                return
            new_dir = os.path.normpath(selected)
            dlg.set_results_dir(new_dir)

        def handle_browse_firmware() -> None:
            """Open file picker and set firmware path field."""
            if not dlg:
                return
            current = dlg.firmware_path_var.get().strip()
            initial_dir = ""
            if current:
                expanded = os.path.expanduser(current)
                if os.path.isdir(expanded):
                    initial_dir = expanded
                elif os.path.isfile(expanded):
                    initial_dir = os.path.dirname(expanded)
            try:
                selected = filedialog.askopenfilename(
                    parent=dlg,
                    initialdir=initial_dir or None,
                    title="Select Firmware Image",
                    filetypes=[("Firmware Image", "*.bin"), ("All Files", "*.*")],
                )
            except Exception as exc:
                self.win.show_toast(f"Could not open file picker: {exc}")
                return
            if not selected:
                return
            dlg.set_firmware_path(os.path.normpath(selected))

        def handle_flash_firmware() -> None:
            """Flash firmware to all configured boxes."""
            if not dlg:
                return
            firmware_path = dlg.firmware_path_var.get().strip()
            if not firmware_path:
                self.win.show_toast("Select a firmware .bin file first.")
                return
            if not self._ensure_adapter():
                return
            uc = self.controller.uc_flash_firmware
            if uc is None:
                self.win.show_toast("Firmware flashing is not available.")
                return
            box_ids = sorted(
                box_id
                for box_id, url in (self.settings_vm.api_base_urls or {}).items()
                if isinstance(url, str) and url.strip()
            )
            try:
                result = uc(box_ids=box_ids, firmware_path=firmware_path)
            except Exception as exc:
                self._toast_error(exc, context="Flash firmware")
                return

            if result.failures:
                failed_boxes = ", ".join(sorted(result.failures.keys()))
                self.win.show_toast(f"Firmware flash failed on {failed_boxes}.")
                details = "\n".join(
                    f"{box_id}: {err}" for box_id, err in result.failures.items()
                )
                messagebox.showerror("Firmware Flash Failed", details, parent=dlg)
                return

            flashed_boxes = ", ".join(sorted(result.successes.keys()))
            if flashed_boxes:
                self.win.show_toast(f"Firmware flashed on {flashed_boxes}.")
            else:
                self.win.show_toast("Firmware flash completed.")

        def handle_open_nas_setup() -> None:
            """Open standalone NAS setup dialog."""
            NASSetupGUI(self.win)

        dlg = SettingsDialog(
            self.win,
            on_test_connection=handle_test_connection,
            on_test_relay=handle_test_relay,
            on_browse_results_dir=handle_browse_results_dir,
            on_browse_firmware=handle_browse_firmware,
            on_discover_devices=lambda: self._on_discover_devices(dlg),
            on_open_nas_setup=handle_open_nas_setup,
            on_save=self._on_settings_saved,
            on_flash_firmware=handle_flash_firmware,
            on_close=lambda: None,
        )

        dlg.set_api_base_urls(self.settings_vm.api_base_urls)
        dlg.set_api_keys(self.settings_vm.api_keys)
        dlg.set_timeouts(
            self.settings_vm.request_timeout_s, self.settings_vm.download_timeout_s
        )
        dlg.set_poll_interval(self.settings_vm.poll_interval_ms)
        dlg.set_poll_backoff_max(self.settings_vm.poll_backoff_max_ms)
        dlg.set_results_dir(self.settings_vm.results_dir)
        dlg.set_experiment_name(self.settings_vm.experiment_name)
        dlg.set_subdir(self.settings_vm.subdir)
        dlg.set_auto_download(self.settings_vm.auto_download_on_complete)
        dlg.set_use_streaming(self.settings_vm.use_streaming)
        dlg.set_debug_logging(self.settings_vm.debug_logging)
        dlg.set_relay_config(self.settings_vm.relay_ip, self.settings_vm.relay_port)
        dlg.set_firmware_path(self.settings_vm.firmware_path)
        dlg.set_save_enabled(self.settings_vm.is_valid())

    def _confirm_https_base_urls(self, payload: dict) -> bool:
        """Warn user when settings contain HTTPS box URLs and allow override."""
        https_urls = tuple(
            sorted(
                (
                    str(box_id),
                    str(url).strip(),
                )
                for box_id, url in (payload.get("api_base_urls") or {}).items()
                if isinstance(url, str) and str(url).strip().lower().startswith("https://")
            )
        )
        if not https_urls:
            return True
        lines = "\n".join(f"- {box}: {url}" for box, url in https_urls)
        warning = (
            "One or more box URLs use HTTPS.\n\n"
            "If your Uvicorn server is running without TLS (default HTTP mode), "
            "this can cause SSL handshake errors (for example: WRONG_VERSION_NUMBER) "
            "and server-side 'invalid HTTP request received' messages.\n\n"
            "Affected URLs:\n"
            f"{lines}\n\n"
            "Click 'OK' to save anyway, or 'Cancel' to review URLs."
        )
        return bool(messagebox.askokcancel("HTTPS URL warning", warning, parent=self.win))

    def _on_settings_saved(self, cfg: dict) -> None:
        """Validate and persist settings payload from the dialog.

        Args:
            cfg: Settings payload emitted by ``SettingsDialog``.
        """
        payload = dict(cfg or {})
        raw_dir = str(payload.get("results_dir") or ".").strip() or "."
        expanded_dir = os.path.expanduser(raw_dir)
        target_dir = os.path.abspath(expanded_dir)

        if not os.path.isdir(target_dir):
            self.win.show_toast(f"Results directory does not exist: {raw_dir}")
            return

        tmp_fd: Optional[int] = None
        tmp_path: str = ""
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=target_dir, prefix="seva_results_dir_", suffix=".tmp"
            )
            os.close(tmp_fd)
            tmp_fd = None
            os.remove(tmp_path)
            tmp_path = ""
        except Exception as exc:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            self.win.show_toast(f"Results directory not writable: {exc}")
            return

        payload["results_dir"] = os.path.normpath(expanded_dir)

        if not self._confirm_https_base_urls(payload):
            return

        try:
            self.settings_vm.apply_dict(payload)
            self.storage.save_user_settings(self.settings_vm.to_dict())
            self._apply_logging_preferences()
        except Exception as exc:
            self.win.show_toast(f"Could not save settings: {exc}")
            return

        self._stop_all_polling()
        self.controller.reset()
        self._apply_box_configuration()
        self.win.show_toast("Settings saved.")


__all__ = ["SettingsController"]
