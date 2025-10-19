"""Cyclic voltammetry parameter mapping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping

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
class CVParams(ModeParams):
    """Normalized CV parameters derived from the experiment form."""

    start: Any
    vertex1: Any
    vertex2: Any
    end: Any
    scan_rate: Any
    cycles: Any
    flags: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "CVParams":
        """Create a params object from the flat CV form snapshot."""

        data: Dict[str, Any] = dict(form or {})
        start = cls._coerce_start(data.get("cv.start_v"))
        return cls(
            start=start,
            vertex1=cls._coerce_float(data.get("cv.vertex1_v")),
            vertex2=cls._coerce_float(data.get("cv.vertex2_v")),
            end=cls._coerce_float(data.get("cv.final_v")),
            scan_rate=cls._coerce_float(data.get("cv.scan_rate_v_s")),
            cycles=cls._coerce_int(data.get("cv.cycles")),
            flags=cls._extract_flags(data),
        )

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the parameters into the REST API payload."""

        return {
            "start": self.start,
            "vertex1": self.vertex1,
            "vertex2": self.vertex2,
            "end": self.end,
            "scan_rate": self.scan_rate,
            "cycles": self.cycles,
        }

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

    @staticmethod
    def _coerce_int(value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return value
            value = stripped
        try:
            return int(float(value))
        except Exception:
            return value

    @classmethod
    def _coerce_start(cls, value: Any) -> Any:
        if value is None:
            return 0.0
        if isinstance(value, str) and not value.strip():
            return 0.0
        return cls._coerce_float(value)

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
