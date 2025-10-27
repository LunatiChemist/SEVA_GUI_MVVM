"""AC mode parameter mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional

from . import ModeParams

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
class ACParamsBridge(ModeParams):
    """Normalized AC-electrolysis parameters derived from the experiment form."""

    duration_s: Any
    frequency_hz: Any
    target: Any
    control_mode: Optional[str]
    charge_cutoff_c: Any
    voltage_cutoff_v: Any

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "ACParamsBridge":
        """Create a params object from the flat AC form snapshot."""

        data: Dict[str, Any] = dict(form or {})
        control_mode = cls._normalize_control_mode(data.get("control_mode"))
        return cls(
            duration_s=cls._coerce_float(data.get("ea.duration_s")),
            frequency_hz=cls._coerce_float(data.get("ea.frequency_hz")),
            target=cls._coerce_float(data.get("ea.target")),
            control_mode=control_mode,
            charge_cutoff_c=cls._coerce_float(data.get("ea.charge_cutoff_c")),
            voltage_cutoff_v=cls._coerce_float(data.get("ea.voltage_cutoff_v")),
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
        self._maybe_set(payload, "duration", self.duration_s)
        self._maybe_set(payload, "potential", self.frequency_hz)
        return payload

    @staticmethod
    def _coerce_float(value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return value
            value = stripped
        try:
            return float(value)
        except Exception:
            return value

    @classmethod
    def _extract_flags(cls, data: Mapping[str, Any]) -> Dict[str, Any]:
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
        return key in _FLAG_KEYS or key.startswith("run_")

    @staticmethod
    def _normalize_control_mode(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None
        if "current" in text:
            return "current"
        if "potential" in text or "voltage" in text:
            return "potential"
        return text

    @staticmethod
    def _maybe_set(target: Dict[str, Any], key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str) and not value.strip():
            return
        target[key] = value

    @staticmethod
    def _is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return False


__all__ = ["ACParams"]
