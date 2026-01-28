from __future__ import annotations

"""Controller for device discovery workflows."""

import logging
from typing import List, Optional, Sequence, Set, TYPE_CHECKING
from urllib.parse import urlparse

from seva.usecases.discover_and_assign_devices import (
    DiscoverAndAssignDevices,
    DiscoveryRequest,
)
from seva.viewmodels.settings_vm import SettingsVM
from seva.domain.ports import StoragePort
from .views.discovery_results_dialog import DiscoveryResultsDialog

if TYPE_CHECKING:  # pragma: no cover
    from .views.settings_dialog import SettingsDialog


class DiscoveryController:
    """Discovery orchestration for settings workflows."""

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

    def discover(self, dialog: Optional["SettingsDialog"] = None) -> None:
        candidates = self._build_discovery_candidates()
        if not candidates:
            self.win.show_toast("No discovery candidates available.")
            return

        current_registry = {
            key: value
            for key, value in (self.settings_vm.api_base_urls or {}).items()
            if value
        }

        result = self.discovery_uc(
            DiscoveryRequest(
                candidates=candidates,
                api_key=None,
                timeout_s=0.5,
                box_ids=self.box_ids,
                existing_registry=current_registry,
            )
        )

        persistence_error: Optional[Exception] = None
        if result.assigned:
            normalized_payload = {
                box_id: result.normalized_registry.get(box_id, "") for box_id in self.box_ids
            }
            try:
                self.settings_vm.api_base_urls = normalized_payload
            except ValueError as exc:
                self.win.show_toast(f"Could not apply discovered devices: {exc}")
                return
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
                rows.append({
                    "base_url": (getattr(box, "base_url", "") or "").strip(),
                    "box_id": getattr(box, "box_id", None),
                    "devices": getattr(box, "devices", None),
                    "api_version": getattr(box, "api_version", None),
                    "build": getattr(box, "build", None),
                })
            DiscoveryResultsDialog(self.win, rows)

    def _build_discovery_candidates(self) -> List[str]:
        candidates: List[str] = []
        base_urls = self.settings_vm.api_base_urls or {}
        for url in base_urls.values():
            value = (url or "").strip()
            if value:
                candidates.append(value)

        cidr_hints: List[str] = []

        for value in candidates:
            parsed = urlparse(value)
            host = parsed.hostname or ""
            if not host:
                continue
            octets = host.split(".")
            if len(octets) != 4:
                continue
            try:
                if all(0 <= int(part) <= 255 for part in octets):
                    cidr_hints.append(".".join(octets[:3]) + ".0/24")
            except ValueError:
                continue

        ordered: List[str] = []
        seen: Set[str] = set()
        for entry in candidates + cidr_hints:
            normalized = entry.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)

        if not ordered:
            ordered.append("192.168.0.0/24")
        return ordered


__all__ = ["DiscoveryController"]
