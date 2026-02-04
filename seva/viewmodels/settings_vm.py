"""Settings dialog state container and typed runtime configuration.

Call context:
    ``SettingsController`` and ``AppController`` read/write this view model to
    configure adapters and use cases. Persistence is delegated to ``StorageLocal``.

This module intentionally owns mutable UI state only; it does not read files,
write files, or perform network calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable, Dict, Mapping, Optional

from ..utils.logging import env_requests_debug

BoxId = str
BOX_IDS: tuple[BoxId, ...] = ("A", "B", "C", "D")


@dataclass
class SettingsConfig:
    """Typed runtime settings persisted by storage adapters.

    Attributes:
        results_dir: Root folder for downloaded artifacts.
        request_timeout_s: HTTP request timeout in seconds.
        download_timeout_s: Download timeout in seconds.
        poll_interval_ms: Base polling interval for group status.
        poll_backoff_max_ms: Maximum backoff interval for polling.
        auto_download_on_complete: Whether completed groups auto-download.
        api_base_urls: Box id -> base URL mapping.
        firmware_path: Selected firmware binary path.
    """

    results_dir: str = "."
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    poll_interval_ms: int = 750
    poll_backoff_max_ms: int = 5000
    auto_download_on_complete: bool = True
    api_base_urls: Dict[BoxId, str] = field(default_factory=dict)
    firmware_path: str = ""


def _default_debug_logging() -> bool:
    """Resolve initial debug logging flag from environment configuration."""
    return env_requests_debug()


class SettingsVM:
    """Own mutable settings dialog state and command callbacks.

    ``SettingsVM`` bridges plain dialog values to ``SettingsConfig`` so
    infrastructure wiring can consume typed values while views stay simple.
    """

    def __init__(
        self,
        *,
        config: Optional[SettingsConfig] = None,
        on_test_connection: Optional[Callable[[BoxId], None]] = None,
        on_test_relay: Optional[Callable[[], None]] = None,
        on_browse_results_dir: Optional[Callable[[], None]] = None,
        on_save: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """Initialize settings state and optional command callbacks.

        Args:
            config: Optional starting typed config.
            on_test_connection: Callback for per-box connectivity checks.
            on_test_relay: Callback for relay connectivity checks.
            on_browse_results_dir: Callback to open folder picker flow.
            on_save: Callback receiving serialized payload on save command.
        """
        self.config = config or SettingsConfig()
        self.on_test_connection = on_test_connection
        self.on_test_relay = on_test_relay
        self.on_browse_results_dir = on_browse_results_dir
        self.on_save = on_save

        self.api_keys: Dict[BoxId, str] = {box: "" for box in BOX_IDS}
        self.experiment_name: str = ""
        self.subdir: str = ""
        self.use_streaming: bool = False
        self.relay_ip: str = ""
        self.relay_port: int = 0
        self.debug_logging: bool = _default_debug_logging()

    # ------------------------------------------------------------------
    # Properties bridging to the typed config
    # ------------------------------------------------------------------
    @property
    def results_dir(self) -> str:
        """Return configured results output directory."""
        return self.config.results_dir

    @results_dir.setter
    def results_dir(self, value: str) -> None:
        """Replace configured results output directory."""
        self.config = replace(self.config, results_dir=value)

    @property
    def request_timeout_s(self) -> int:
        """Return HTTP request timeout in seconds."""
        return self.config.request_timeout_s

    @request_timeout_s.setter
    def request_timeout_s(self, value: int) -> None:
        """Replace HTTP request timeout in seconds."""
        self.config = replace(self.config, request_timeout_s=value)

    @property
    def download_timeout_s(self) -> int:
        """Return download timeout in seconds."""
        return self.config.download_timeout_s

    @download_timeout_s.setter
    def download_timeout_s(self, value: int) -> None:
        """Replace download timeout in seconds."""
        self.config = replace(self.config, download_timeout_s=value)

    @property
    def poll_interval_ms(self) -> int:
        """Return base polling interval in milliseconds."""
        return self.config.poll_interval_ms

    @poll_interval_ms.setter
    def poll_interval_ms(self, value: int) -> None:
        """Replace base polling interval in milliseconds."""
        self.config = replace(self.config, poll_interval_ms=value)

    @property
    def poll_backoff_max_ms(self) -> int:
        """Return maximum polling backoff in milliseconds."""
        return self.config.poll_backoff_max_ms

    @poll_backoff_max_ms.setter
    def poll_backoff_max_ms(self, value: int) -> None:
        """Replace maximum polling backoff in milliseconds."""
        self.config = replace(self.config, poll_backoff_max_ms=value)

    @property
    def auto_download_on_complete(self) -> bool:
        """Return whether downloads should auto-start on completion."""
        return self.config.auto_download_on_complete

    @auto_download_on_complete.setter
    def auto_download_on_complete(self, value: bool) -> None:
        """Replace auto-download flag for completed groups."""
        self.config = replace(self.config, auto_download_on_complete=bool(value))

    @property
    def api_base_urls(self) -> Dict[BoxId, str]:
        """Return box id to API base URL mapping."""
        return self.config.api_base_urls

    @api_base_urls.setter
    def api_base_urls(self, value: Mapping[BoxId, Any]) -> None:
        """Replace box id to API base URL mapping."""
        self.config = replace(self.config, api_base_urls=dict(value or {}))

    @property
    def firmware_path(self) -> str:
        """Return selected firmware binary path."""
        return self.config.firmware_path

    @firmware_path.setter
    def firmware_path(self, value: str) -> None:
        """Replace selected firmware binary path."""
        self.config = replace(self.config, firmware_path=str(value or ""))

    # ------------------------------------------------------------------
    def is_valid(self) -> bool:
        """Return whether current settings are syntactically valid.

        Current behavior is permissive and returns ``True``. Validation rules
        are enforced in controller/use-case layers where context is available.
        """
        return True

    def apply_dict(self, payload: Mapping[str, Any]) -> None:
        """Apply persisted settings payload to current view model state.

        Call chain:
            ``App._load_user_settings`` -> ``SettingsVM.apply_dict``.

        Args:
            payload: Deserialized settings payload from storage.

        Side Effects:
            Replaces typed config fields and mutable dialog-only fields.
        """
        if not isinstance(payload, Mapping):
            return

        updates: Dict[str, Any] = {}
        for cfg_key in SettingsConfig.__annotations__.keys():
            if cfg_key in payload:
                updates[cfg_key] = payload[cfg_key]

        if updates:
            self.config = replace(self.config, **updates)

        if "api_keys" in payload:
            self.api_keys = dict(payload.get("api_keys") or {})

        if "experiment_name" in payload:
            self.experiment_name = str(payload.get("experiment_name") or "")

        if "subdir" in payload:
            self.subdir = str(payload.get("subdir") or "")

        if "use_streaming" in payload:
            self.use_streaming = bool(payload.get("use_streaming"))

        if "debug_logging" in payload:
            self.debug_logging = bool(payload.get("debug_logging"))

        if "relay_ip" in payload:
            self.relay_ip = str(payload.get("relay_ip") or "")

        if "relay_port" in payload:
            self.relay_port = int(payload.get("relay_port") or 0)

        if "firmware_path" in payload:
            self.firmware_path = str(payload.get("firmware_path") or "")

    def to_dict(self) -> dict:
        """Serialize current settings state for persistence and callback handoff."""
        snapshot = asdict(self.config)
        snapshot.update(
            {
                "api_keys": dict(self.api_keys),
                "experiment_name": self.experiment_name,
                "subdir": self.subdir,
                "use_streaming": bool(self.use_streaming),
                "debug_logging": bool(self.debug_logging),
                "relay_ip": self.relay_ip,
                "relay_port": self.relay_port,
                "firmware_path": self.firmware_path,
            }
        )
        return snapshot

    def set_results_dir(self, path: str) -> None:
        """Set results directory helper used by dialog callbacks."""
        self.results_dir = path

    def set_debug_logging(self, enabled: bool) -> None:
        """Set debug logging flag helper used by dialog callbacks."""
        self.debug_logging = bool(enabled)

    def cmd_save(self) -> None:
        """Emit save command with serialized payload.

        Call chain:
            Settings dialog save action -> ``SettingsVM.cmd_save`` -> controller
            callback that persists payload and reapplies adapter wiring.
        """
        if self.on_save:
            self.on_save(self.to_dict())

    def set_experiment_name(self, name: str) -> None:
        """Update default experiment-name field used by plan building."""
        self.experiment_name = str(name or "")

    def set_subdir(self, value: str) -> None:
        """Update optional subdirectory hint used by storage metadata builder."""
        self.subdir = str(value or "")


def default_settings_payload() -> dict:
    """Return a fresh serialized payload using default settings values."""
    return SettingsVM().to_dict()
