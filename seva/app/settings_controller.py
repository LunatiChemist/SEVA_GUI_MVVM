"""Controller for settings dialog actions and persistence updates.

This module keeps settings workflow orchestration out of views by handling
dialog callbacks, validation, persistence, and side effects (adapter resets,
polling restarts, and box-configuration reapplication).
"""

from __future__ import annotations


import logging
import os
import tempfile
import time
from typing import Callable, Optional
from tkinter import filedialog, messagebox

from seva.domain.box_version import BoxVersionInfo
from seva.domain.ports import StoragePort, UseCaseError
from seva.domain.remote_update import UpdateStartReceipt
from seva.viewmodels.settings_vm import SettingsVM
from seva.app.controller import AppController
from seva.app.nas_gui_smb import NASSetupGUI
from seva.app.views.settings_dialog import SettingsDialog
from seva.app.views.update_progress_dialog import UpdateProgressDialog


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

        def handle_browse_update_package() -> None:
            """Open file picker and set update package path field."""
            if not dlg:
                return
            current = dlg.update_package_path_var.get().strip()
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
                    title="Select Update Package",
                    filetypes=[("Update Package", "*.zip"), ("All Files", "*.*")],
                )
            except Exception as exc:
                self.win.show_toast(f"Could not open file picker: {exc}")
                return
            if not selected:
                return
            dlg.set_update_package_path(os.path.normpath(selected))

        def handle_start_package_update() -> None:
            """Start remote package update and open strict modal progress view."""
            if not dlg:
                return
            package_path = dlg.update_package_path_var.get().strip()
            if not package_path:
                self.win.show_toast("Select an update .zip package first.")
                return
            if not self._ensure_adapter():
                return
            start_uc = self.controller.uc_start_remote_update
            poll_uc = self.controller.uc_poll_remote_update
            if start_uc is None or poll_uc is None:
                self.win.show_toast("Remote package update is not available.")
                return
            box_ids = sorted(
                box_id
                for box_id, url in (self.settings_vm.api_base_urls or {}).items()
                if isinstance(url, str) and url.strip()
            )
            if not box_ids:
                self.win.show_toast("Configure at least one box URL before updating.")
                return
            try:
                start_result = start_uc(box_ids=box_ids, package_path=package_path)
            except Exception as exc:
                self._toast_error(exc, context="Start remote update")
                return

            if start_result.failures and not start_result.started:
                details = "\n".join(
                    f"{box_id}: {reason}" for box_id, reason in sorted(start_result.failures.items())
                )
                messagebox.showerror("Remote Update Failed", details, parent=dlg)
                self.win.show_toast("Remote update failed to start.")
                return

            progress = UpdateProgressDialog(self.win)
            self._poll_remote_updates(
                modal=progress,
                started=start_result.started,
                start_failures=start_result.failures,
            )

        def handle_refresh_versions() -> None:
            """Refresh returned version/health info for all configured boxes."""
            if not dlg:
                return
            if not self._ensure_adapter():
                return
            refresh_uc = self.controller.uc_refresh_box_versions
            if refresh_uc is None:
                self.win.show_toast("Version refresh is not available.")
                return
            box_ids = sorted(
                box_id
                for box_id, url in (self.settings_vm.api_base_urls or {}).items()
                if isinstance(url, str) and url.strip()
            )
            if not box_ids:
                self.win.show_toast("Configure at least one box URL before refreshing versions.")
                return
            dlg.set_version_info_text("Refreshing version data...")
            try:
                result = refresh_uc(box_ids=box_ids)
            except Exception as exc:
                self._toast_error(exc, context="Refresh versions")
                return

            text = self._format_version_info_output(infos=result.infos, failures=result.failures)
            self.settings_vm.version_info_text = text
            dlg.set_version_info_text(text)
            if result.failures:
                self.win.show_toast("Version info refreshed with failures.")
            else:
                self.win.show_toast("Version info refreshed.")

        def handle_open_nas_setup() -> None:
            """Open standalone NAS setup dialog."""
            NASSetupGUI(self.win)

        dlg = SettingsDialog(
            self.win,
            on_test_connection=handle_test_connection,
            on_test_relay=handle_test_relay,
            on_browse_results_dir=handle_browse_results_dir,
            on_browse_update_package=handle_browse_update_package,
            on_discover_devices=lambda: self._on_discover_devices(dlg),
            on_open_nas_setup=handle_open_nas_setup,
            on_save=self._on_settings_saved,
            on_start_package_update=handle_start_package_update,
            on_refresh_versions=handle_refresh_versions,
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
        dlg.set_update_package_path(self.settings_vm.update_package_path)
        dlg.set_version_info_text(self.settings_vm.version_info_text)
        dlg.set_save_enabled(self.settings_vm.is_valid())

    @staticmethod
    def _format_version_info_output(
        *,
        infos: dict[str, BoxVersionInfo],
        failures: dict[str, str],
    ) -> str:
        """Format per-box version refresh data into a compact one-line string."""
        all_boxes = sorted(set(infos.keys()) | set(failures.keys()))
        if not all_boxes:
            return "No boxes were queried."

        lines: list[str] = []
        for box_id in all_boxes:
            failure = failures.get(box_id)
            if failure:
                lines.append(f"{box_id}(error={failure})")
                continue

            info = infos.get(box_id)
            if info is None:
                lines.append(f"{box_id}(error=No data returned)")
                continue

            health_label = "unknown"
            if info.health_ok is True:
                health_label = "ok"
            elif info.health_ok is False:
                health_label = "failed"
            devices = "?" if info.health_devices is None else str(info.health_devices)
            reported_box = info.reported_box_id or "-"
            api_version = info.api_version or "-"
            pybeep_version = info.pybeep_version or "-"
            firmware_version = info.firmware_version or "-"
            python_version = info.python_version or "-"
            build_identifier = info.build_identifier or "-"
            lines.append(
                f"{box_id}(api={api_version},pybeep={pybeep_version},firmware={firmware_version},python={python_version},"
                f"build={build_identifier},health={health_label},devices={devices},box_id={reported_box})"
            )

        return " | ".join(lines)

    def _poll_remote_updates(
        self,
        *,
        modal: UpdateProgressDialog,
        started: dict[str, UpdateStartReceipt],
        start_failures: dict[str, str],
    ) -> None:
        """Poll update status and keep strict modal progress synchronized."""
        poll_uc = self.controller.uc_poll_remote_update
        if poll_uc is None:
            modal.set_overview(
                summary="Remote update polling unavailable.",
                step="poll_unavailable",
                heartbeat_text="-",
                liveness="Polling use case is not configured.",
            )
            modal.mark_terminal(summary="Remote update polling unavailable.")
            return

        started_map = {str(box): receipt for box, receipt in (started or {}).items() if str(box).strip()}
        startup_failures = {str(box): str(reason) for box, reason in (start_failures or {}).items()}
        poll_interval_ms = max(1000, int(self.settings_vm.poll_interval_ms or 1000))
        terminal_announced = {"done": False}

        def _tick() -> None:
            if not modal.winfo_exists():
                return

            poll_failures: dict[str, str] = {}
            statuses = {}
            if started_map:
                try:
                    poll_result = poll_uc(started=started_map)
                    statuses = dict(poll_result.statuses or {})
                    poll_failures = dict(poll_result.failures or {})
                except Exception as exc:
                    message = str(exc) or "Polling failed."
                    poll_failures = {box: message for box in started_map.keys()}

            any_failures = bool(startup_failures or poll_failures)
            rows = []
            heartbeat_candidates: list[str] = []
            running_step = "queued"
            all_started_terminal = True
            any_running = False

            all_boxes = sorted(set(started_map.keys()) | set(startup_failures.keys()))
            for box_id in all_boxes:
                if box_id in startup_failures and box_id not in started_map:
                    rows.append((box_id, "failed", "start_failed", startup_failures[box_id], "-"))
                    continue

                if box_id in poll_failures:
                    rows.append((box_id, "failed", "poll_failed", poll_failures[box_id], "-"))
                    continue

                snapshot = statuses.get(box_id)
                if snapshot is None:
                    all_started_terminal = False
                    any_running = True
                    rows.append((box_id, "running", "awaiting_status", "Waiting for status response.", "-"))
                    continue

                status_label = snapshot.status or "queued"
                step_label = snapshot.step or "queued"
                message_text = snapshot.message or snapshot.error.get("message", "")
                heartbeat_text = snapshot.heartbeat_at or snapshot.observed_at or "-"
                rows.append((box_id, status_label, step_label, message_text, heartbeat_text))

                if heartbeat_text and heartbeat_text != "-":
                    heartbeat_candidates.append(heartbeat_text)
                if snapshot.status in ("queued", "running"):
                    any_running = True
                    running_step = step_label
                    all_started_terminal = False

            if not started_map:
                all_started_terminal = True

            heartbeat_text = heartbeat_candidates[-1] if heartbeat_candidates else "-"
            liveness = f"Still running heartbeat observed at {time.strftime('%H:%M:%S')}."
            if any_running:
                summary_text = "Remote update is running. Keep this dialog open."
            elif any_failures:
                summary_text = "Remote update finished with failures."
            else:
                summary_text = "Remote update completed."

            modal.set_overview(
                summary=summary_text,
                step=running_step if any_running else "terminal",
                heartbeat_text=heartbeat_text,
                liveness=liveness,
            )
            modal.set_rows(rows)

            if all_started_terminal:
                if not terminal_announced["done"]:
                    terminal_announced["done"] = True
                    if any_failures:
                        details = "\n".join(
                            f"{box}: {reason}" for box, reason in sorted({**startup_failures, **poll_failures}.items())
                        )
                        if details:
                            messagebox.showerror("Remote Update Failures", details, parent=modal)
                        self.win.show_toast("Remote update finished with failures.")
                    else:
                        self.win.show_toast("Remote update completed.")
                modal.mark_terminal(summary=summary_text)
                return

            self.win.after(poll_interval_ms, _tick)

        _tick()

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
