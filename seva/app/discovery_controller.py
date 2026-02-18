"""Controller that orchestrates asynchronous mDNS discovery from settings UI."""

from __future__ import annotations

import logging
import threading
from typing import Optional, Sequence, TYPE_CHECKING

from seva.usecases.discover_and_assign_devices import DiscoverAndAssignDevices, DiscoveryRequest
from seva.viewmodels.settings_vm import SettingsVM
from seva.domain.ports import StoragePort
from seva.app.views.discovery_results_dialog import DiscoveryResultsDialog

if TYPE_CHECKING:  # pragma: no cover
    from seva.app.views.settings_dialog import SettingsDialog


class DiscoveryController:
    """Run device discovery workflow and update settings state/UI."""

    def __init__(
        self,
        *,
        win,
        settings_vm: SettingsVM,
        storage: StoragePort,
        discovery_uc: DiscoverAndAssignDevices,
        box_ids: Sequence[str],
    ) -> None:
        self._log = logging.getLogger(__name__)
        self.win = win
        self.settings_vm = settings_vm
        self.storage = storage
        self.discovery_uc = discovery_uc
        self.box_ids = list(box_ids)
        self._running = False

    def discover(self, dialog: Optional["SettingsDialog"] = None) -> None:
        """Run discovery in a worker thread to keep the GUI responsive."""
        if self._running:
            return

        self._running = True
        self.win.show_toast("Gerätesuche läuft...")

        def worker() -> None:
            error: Optional[Exception] = None
            result = None
            try:
                current_registry = {
                    key: value
                    for key, value in (self.settings_vm.api_base_urls or {}).items()
                    if value
                }
                result = self.discovery_uc(
                    DiscoveryRequest(
                        duration_s=2.5,
                        health_timeout_s=0.6,
                        box_ids=self.box_ids,
                        existing_registry=current_registry,
                    )
                )
            except Exception as exc:  # mapped by use case
                error = exc

            self.win.after(0, lambda: self._finish(dialog=dialog, result=result, error=error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, *, dialog: Optional["SettingsDialog"], result, error: Optional[Exception]) -> None:
        """Apply discovery outcome back on GUI thread and persist settings."""
        self._running = False

        if error is not None:
            self._log.error("Discovery failed", exc_info=(type(error), error, error.__traceback__))
            self.win.show_toast(str(error))
            return
        if result is None:
            self.win.show_toast("Discovery finished. No devices found.")
            return

        persistence_error: Optional[Exception] = None
        if result.assigned:
            normalized_payload = {
                box_id: result.normalized_registry.get(box_id, "") for box_id in self.box_ids
            }
            self.settings_vm.api_base_urls = normalized_payload
            try:
                self.storage.save_user_settings(self.settings_vm.to_dict())
            except Exception as exc:
                persistence_error = exc
                self._log.exception("Failed to persist discovered devices")

            if dialog and dialog.winfo_exists():
                dialog.set_api_base_urls(normalized_payload)
                dialog.set_save_enabled(self.settings_vm.is_valid())

        message = result.message
        if persistence_error:
            message = f"{message}; Persistence failed ({persistence_error})"
        self.win.show_toast(message)

        if result.discovered:
            rows = []
            for box in result.discovered:
                rows.append(
                    {
                        "name": box.name,
                        "ip": box.ip,
                        "port": box.port,
                        "health_url": box.health_url,
                        "properties": dict(box.properties),
                    }
                )
            DiscoveryResultsDialog(self.win, rows)


__all__ = ["DiscoveryController"]
