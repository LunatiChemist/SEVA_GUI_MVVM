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


    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "CVParams":
        """Create a params object from the flat CV form snapshot."""

        data: Dict[str, Any] = dict(form or {})
        return cls(
            start=data.get("cv.start_v") or 0.0,
            vertex1=data.get("cv.vertex1_v"),
            vertex2=data.get("cv.vertex2_v"),
            end=data.get("cv.final_v"),
            scan_rate=data.get("cv.scan_rate_v_s"),
            cycles=data.get("cv.cycles"),
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
