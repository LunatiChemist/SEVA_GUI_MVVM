from __future__ import annotations

"""Central registry for mode normalization, labels, and clipboard rules."""

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .params import ACParams, CVParams, ModeParams
from .util import normalize_mode_name


@dataclass(frozen=True)
class ModeRule:
    """Definition of UI filtering rules for a single mode."""

    name: str
    prefixes: Tuple[str, ...]
    flags: Tuple[str, ...]
    extras: Tuple[str, ...]
    clipboard_attr: str
    label: str


class ModeRegistry:
    """Registry for mode-specific UI and payload handling."""

    def __init__(
        self,
        rules: Mapping[str, ModeRule],
        builders: Optional[Mapping[str, type[ModeParams]]] = None,
    ) -> None:
        self._rules: Dict[str, ModeRule] = {
            self._normalize_key(key): rule for key, rule in rules.items()
        }
        self._builders: Dict[str, type[ModeParams]] = {
            self._normalize_key(key): builder for key, builder in (builders or {}).items()
        }

    @classmethod
    def default(cls) -> "ModeRegistry":
        rules = {
            "CV": ModeRule(
                name="CV",
                prefixes=("cv.",),
                flags=("run_cv",),
                extras=(),
                clipboard_attr="clipboard_cv",
                label="CV",
            ),
            "DCAC": ModeRule(
                name="DCAC",
                prefixes=("ea.",),
                flags=("run_dc", "run_ac"),
                extras=("control_mode", "ea.target"),
                clipboard_attr="clipboard_dcac",
                label="DC/AC",
            ),
            "CDL": ModeRule(
                name="CDL",
                prefixes=("cdl.",),
                flags=("eval_cdl",),
                extras=(),
                clipboard_attr="clipboard_cdl",
                label="CDL",
            ),
            "EIS": ModeRule(
                name="EIS",
                prefixes=("eis.",),
                flags=("run_eis",),
                extras=(),
                clipboard_attr="clipboard_eis",
                label="EIS",
            ),
        }
        builders = {
            "CV": CVParams,
            "AC": ACParams,
        }
        return cls(rules=rules, builders=builders)

    def rules(self) -> Iterable[ModeRule]:
        return self._rules.values()

    def rule_for(self, mode: str) -> ModeRule:
        key = self._normalize_key(mode)
        rule = self._rules.get(key)
        if not rule:
            raise ValueError(f"Unsupported mode: {mode}")
        return rule

    def label_for(self, mode: str) -> str:
        try:
            return self.rule_for(mode).label
        except ValueError:
            return str(mode)

    def clipboard_attr_for(self, mode: str) -> str:
        return self.rule_for(mode).clipboard_attr

    def is_mode_field(self, mode: str, field_id: str) -> bool:
        rule = self.rule_for(mode)
        return (
            field_id in rule.flags
            or field_id in rule.extras
            or any(field_id.startswith(prefix) for prefix in rule.prefixes)
        )

    def filter_fields(self, mode: str, fields: Mapping[str, str]) -> Dict[str, str]:
        rule = self.rule_for(mode)
        snapshot = {
            fid: val for fid, val in fields.items() if self.is_mode_field(mode, fid)
        }
        for flag in rule.flags:
            snapshot[flag] = "1"
        return snapshot

    def builder_for(self, mode: str) -> Optional[type[ModeParams]]:
        return self._builders.get(self._normalize_key(mode))

    def backend_token(self, mode: str) -> str:
        return normalize_mode_name(mode)

    @staticmethod
    def _normalize_key(mode: str) -> str:
        return str(mode or "").strip().upper()


__all__ = ["ModeRegistry", "ModeRule"]
