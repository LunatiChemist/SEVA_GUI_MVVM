from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable, Dict, Mapping, Optional

from ..utils.logging import env_requests_debug

BoxId = str
BOX_IDS: tuple[BoxId, ...] = ("A", "B", "C", "D")


@dataclass
class SettingsConfig:
    """Typed runtime settings that persist via StorageLocal."""

    results_dir: str = "."
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    poll_interval_ms: int = 750
    poll_backoff_max_ms: int = 5000
    auto_download_on_complete: bool = True
    api_base_urls: Dict[BoxId, str] = field(default_factory=dict)


def _default_debug_logging() -> bool:
    return env_requests_debug()


class SettingsVM:
    """Keeps app settings UI state (lightweight), no I/O here."""

    def __init__(
        self,
        *,
        config: Optional[SettingsConfig] = None,
        on_test_connection: Optional[Callable[[BoxId], None]] = None,
        on_test_relay: Optional[Callable[[], None]] = None,
        on_browse_results_dir: Optional[Callable[[], None]] = None,
        on_save: Optional[Callable[[dict], None]] = None,
    ) -> None:
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
        return self.config.results_dir

    @results_dir.setter
    def results_dir(self, value: str) -> None:
        self.config = replace(self.config, results_dir=self._normalize_dir(value))

    @property
    def request_timeout_s(self) -> int:
        return self.config.request_timeout_s

    @request_timeout_s.setter
    def request_timeout_s(self, value: int) -> None:
        self.config = replace(self.config, request_timeout_s=self._normalize_int(value, self.request_timeout_s))

    @property
    def download_timeout_s(self) -> int:
        return self.config.download_timeout_s

    @download_timeout_s.setter
    def download_timeout_s(self, value: int) -> None:
        self.config = replace(self.config, download_timeout_s=self._normalize_int(value, self.download_timeout_s))

    @property
    def poll_interval_ms(self) -> int:
        return self.config.poll_interval_ms

    @poll_interval_ms.setter
    def poll_interval_ms(self, value: int) -> None:
        self.config = replace(self.config, poll_interval_ms=self._normalize_int(value, self.poll_interval_ms))

    @property
    def poll_backoff_max_ms(self) -> int:
        return self.config.poll_backoff_max_ms

    @poll_backoff_max_ms.setter
    def poll_backoff_max_ms(self, value: int) -> None:
        self.config = replace(self.config, poll_backoff_max_ms=self._normalize_int(value, self.poll_backoff_max_ms))

    @property
    def auto_download_on_complete(self) -> bool:
        return self.config.auto_download_on_complete

    @auto_download_on_complete.setter
    def auto_download_on_complete(self, value: bool) -> None:
        self.config = replace(self.config, auto_download_on_complete=self._normalize_bool(value))

    @property
    def api_base_urls(self) -> Dict[BoxId, str]:
        return self.config.api_base_urls

    @api_base_urls.setter
    def api_base_urls(self, value: Mapping[BoxId, Any]) -> None:
        self.config = replace(self.config, api_base_urls=self._normalize_box_map(value))

    # ------------------------------------------------------------------
    def is_valid(self) -> bool:
        return True

    def apply_dict(self, payload: Mapping[str, Any]) -> None:
        """Apply persisted settings to the view-model."""

        if not isinstance(payload, Mapping):
            return

        updates: Dict[str, Any] = {}
        for cfg_key in SettingsConfig.__annotations__.keys():
            if cfg_key in payload:
                updates[cfg_key] = self._normalize_config_value(cfg_key, payload[cfg_key])

        if updates:
            self.config = replace(self.config, **updates)

        if "api_keys" in payload:
            self.api_keys = self._normalize_box_map(payload.get("api_keys"))

        if "experiment_name" in payload:
            self.experiment_name = self._normalize_str(payload.get("experiment_name"))

        if "subdir" in payload:
            self.subdir = self._normalize_str(payload.get("subdir"))

        if "use_streaming" in payload:
            self.use_streaming = self._normalize_bool(payload.get("use_streaming"))

        if "debug_logging" in payload:
            self.debug_logging = self._normalize_bool(payload.get("debug_logging"))

        if "relay_ip" in payload:
            self.relay_ip = self._normalize_str(payload.get("relay_ip"))

        if "relay_port" in payload:
            self.relay_port = self._normalize_int(payload.get("relay_port"), self.relay_port)

    def to_dict(self) -> dict:
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
            }
        )
        return snapshot

    def set_results_dir(self, path: str) -> None:
        self.results_dir = path

    def set_debug_logging(self, enabled: bool) -> None:
        self.debug_logging = self._normalize_bool(enabled)

    def cmd_save(self) -> None:
        if self.on_save:
            self.on_save(self.to_dict())

    def set_experiment_name(self, name: str) -> None:
        self.experiment_name = self._normalize_str(name)

    def set_subdir(self, value: str) -> None:
        self.subdir = self._normalize_str(value)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalize_config_value(self, key: str, raw: Any) -> Any:
        if key == "results_dir":
            return self._normalize_dir(raw)
        if key in {
            "request_timeout_s",
            "download_timeout_s",
            "poll_interval_ms",
            "poll_backoff_max_ms",
        }:
            current = getattr(self.config, key)
            return self._normalize_int(raw, current)
        if key == "auto_download_on_complete":
            return self._normalize_bool(raw)
        if key == "api_base_urls":
            return self._normalize_box_map(raw)
        return raw

    @staticmethod
    def _normalize_dir(value: Any) -> str:
        text = "" if value is None else str(value)
        normalized = text.strip() or "."
        return normalized

    @staticmethod
    def _normalize_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _normalize_int(value: Any, fallback: int) -> int:
        if isinstance(value, bool):
            return fallback
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except (TypeError, ValueError):
                return fallback
        return fallback

    @staticmethod
    def _normalize_box_map(value: Any) -> Dict[BoxId, str]:
        if not isinstance(value, Mapping):
            return {}
        normalized: Dict[BoxId, str] = {}
        for raw_key, raw_val in value.items():
            key = str(raw_key)
            normalized[key] = "" if raw_val is None else str(raw_val).strip()
        return normalized


def default_settings_payload() -> dict:
    """Return a fresh snapshot containing the default settings payload."""
    return SettingsVM().to_dict()
