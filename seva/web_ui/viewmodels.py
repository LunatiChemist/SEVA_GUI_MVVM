"""Thin web-facing viewmodels for NiceGUI bindings.

These viewmodels hold browser form state and translate to/from existing core
viewmodels without adding I/O or orchestration logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, Mapping

from seva.viewmodels.settings_vm import BOX_IDS, SettingsVM


BROWSER_SETTINGS_KEY = "seva.web.settings.v1"


def _as_int(value: Any, default: int) -> int:
    """Convert mixed values to int with deterministic fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass
class WebSettingsVM:
    """Browser-editable settings projection for NiceGUI forms."""

    api_base_urls: Dict[str, str] = field(
        default_factory=lambda: {box: "" for box in BOX_IDS}
    )
    api_keys: Dict[str, str] = field(default_factory=lambda: {box: "" for box in BOX_IDS})
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    poll_interval_ms: int = 750
    poll_backoff_max_ms: int = 5000
    results_dir: str = "."
    auto_download_on_complete: bool = True
    experiment_name: str = ""
    subdir: str = ""
    use_streaming: bool = False
    debug_logging: bool = False
    relay_ip: str = ""
    relay_port: int = 0
    firmware_path: str = ""

    @classmethod
    def from_settings_vm(cls, settings_vm: SettingsVM) -> "WebSettingsVM":
        """Build browser form state from the core ``SettingsVM`` snapshot."""
        payload = settings_vm.to_dict()
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "WebSettingsVM":
        """Build browser form state from a settings payload mapping.

        The payload shape matches ``SettingsVM.to_dict`` and supports legacy
        payloads passed to ``SettingsVM.apply_dict``.
        """
        if not isinstance(payload, Mapping):
            raise ValueError("Settings payload must be a mapping.")
        box_urls = {box: str((payload.get("api_base_urls") or {}).get(box, "") or "") for box in BOX_IDS}
        box_keys = {box: str((payload.get("api_keys") or {}).get(box, "") or "") for box in BOX_IDS}
        return cls(
            api_base_urls=box_urls,
            api_keys=box_keys,
            request_timeout_s=_as_int(payload.get("request_timeout_s"), 10),
            download_timeout_s=_as_int(payload.get("download_timeout_s"), 60),
            poll_interval_ms=_as_int(payload.get("poll_interval_ms"), 750),
            poll_backoff_max_ms=_as_int(payload.get("poll_backoff_max_ms"), 5000),
            results_dir=str(payload.get("results_dir") or "."),
            auto_download_on_complete=bool(payload.get("auto_download_on_complete", True)),
            experiment_name=str(payload.get("experiment_name") or ""),
            subdir=str(payload.get("subdir") or ""),
            use_streaming=bool(payload.get("use_streaming")),
            debug_logging=bool(payload.get("debug_logging")),
            relay_ip=str(payload.get("relay_ip") or ""),
            relay_port=_as_int(payload.get("relay_port"), 0),
            firmware_path=str(payload.get("firmware_path") or ""),
        )

    def to_payload(self) -> Dict[str, Any]:
        """Serialize browser form state using ``SettingsVM`` payload shape."""
        return {
            "api_base_urls": {box: str(self.api_base_urls.get(box, "") or "") for box in BOX_IDS},
            "api_keys": {box: str(self.api_keys.get(box, "") or "") for box in BOX_IDS},
            "request_timeout_s": _as_int(self.request_timeout_s, 10),
            "download_timeout_s": _as_int(self.download_timeout_s, 60),
            "poll_interval_ms": _as_int(self.poll_interval_ms, 750),
            "poll_backoff_max_ms": _as_int(self.poll_backoff_max_ms, 5000),
            "results_dir": str(self.results_dir or "."),
            "auto_download_on_complete": bool(self.auto_download_on_complete),
            "experiment_name": str(self.experiment_name or ""),
            "subdir": str(self.subdir or ""),
            "use_streaming": bool(self.use_streaming),
            "debug_logging": bool(self.debug_logging),
            "relay_ip": str(self.relay_ip or ""),
            "relay_port": _as_int(self.relay_port, 0),
            "firmware_path": str(self.firmware_path or ""),
        }

    def apply_to_settings_vm(self, settings_vm: SettingsVM) -> None:
        """Push browser form values into the core settings viewmodel."""
        settings_vm.apply_dict(self.to_payload())


def parse_settings_json(text: str) -> Dict[str, Any]:
    """Parse imported settings JSON into a mapping payload."""
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("Imported settings must be a JSON object.")
    return dict(raw)


@dataclass
class WebNasVM:
    """Form state for NAS workflows in the web runtime."""

    box_id: str = "A"
    host: str = ""
    share: str = ""
    username: str = ""
    password: str = ""
    base_subdir: str = ""
    retention_days: int = 14
    domain: str = ""
    run_id: str = ""
