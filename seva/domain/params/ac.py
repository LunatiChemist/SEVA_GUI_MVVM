"""AC mode parameter mapping from UI form snapshots to typed payload fields.

`ModeRegistry` resolves this builder for AC/DC workflows so the use-case layer
can construct API payloads from a validated domain object instead of raw form
dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional

from seva.domain.params import ModeParams

_FLAG_KEYS = (
    "run_cv",
    "run_dc",
    "run_ac",
    "run_eis",
    "run_lsv",
    "run_cdl",
    "eval_cdl",
)


@dataclass(frozen=True)
class ACParams(ModeParams):
    """Normalized AC-electrolysis parameters derived from the experiment form."""

    duration_s: Any
    frequency_hz: Any
    target: Any
    control_mode: Optional[str]
    charge_cutoff_c: Any
    voltage_cutoff_v: Any

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "ACParams":
        """Create a params object from the flat AC form snapshot."""

        data: Dict[str, Any] = dict(form or {})
        return cls(
            duration_s=data.get("ea.duration_s"),
            frequency_hz=data.get("ea.frequency_hz"),
            target=data.get("ea.target"),
            control_mode=data.get("control_mode"),
            charge_cutoff_c=data.get("ea.charge_cutoff_c"),
            voltage_cutoff_v=data.get("ea.voltage_cutoff_v"),
            flags=cls._extract_flags(data),
        )

    @property
    def voltage_v(self) -> Any:
        """Best-effort voltage value for APIs expecting a voltage target."""

        if self.control_mode == "potential" and not self._is_empty(self.target):
            return self.target
        if not self._is_empty(self.voltage_cutoff_v):
            return self.voltage_cutoff_v
        return self.target

    @property
    def current_ma(self) -> Any:
        """Current setpoint exposed when the control mode is current-based."""

        if self.control_mode == "current" and not self._is_empty(self.target):
            return self.target
        return None

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the parameters into the REST API payload."""

        payload: Dict[str, Any] = {}
        self._maybe_set(payload, "duration_s", self.duration_s)
        self._maybe_set(payload, "frequency_hz", self.frequency_hz)
        self._maybe_set(payload, "voltage_v", self.voltage_v)
        current = self.current_ma
        if current is not None:
            payload["current_ma"] = current
        self._maybe_set(payload, "charge_cutoff_c", self.charge_cutoff_c)
        self._maybe_set(payload, "voltage_cutoff_v", self.voltage_cutoff_v)
        if self.control_mode:
            payload["control_mode"] = self.control_mode
        return payload

    @classmethod
    def _extract_flags(cls, data: Mapping[str, Any]) -> Dict[str, Any]:
        """Collect mode flags from nested and flat form snapshots."""
        flags: Dict[str, Any] = {}
        nested = data.get("flags")
        if isinstance(nested, MutableMapping):
            for key, val in nested.items():
                if cls._is_flag_key(key):
                    flags[key] = val
        for key, val in data.items():
            if cls._is_flag_key(key):
                flags[key] = val
        return dict(flags)

    @staticmethod
    def _is_flag_key(key: str) -> bool:
        """Return whether a field key should be treated as a run flag."""
        return key in _FLAG_KEYS or key.startswith("run_")

    @staticmethod
    def _maybe_set(target: Dict[str, Any], key: str, value: Any) -> None:
        """Write a key/value only when the value is non-empty."""
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        target[key] = value

    @staticmethod
    def _is_empty(value: Any) -> bool:
        """Return whether a candidate value should be treated as empty."""
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return False


__all__ = ["ACParams"]
