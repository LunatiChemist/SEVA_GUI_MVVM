"""Central registry for mode normalization, labels, and mode-field ownership.

ViewModels call this registry to determine which form fields belong to each
mode and which builder class should construct a typed `ModeParams` object.
Use cases then consume those typed params for payload construction.
"""

from __future__ import annotations


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
        """Store normalized rule and builder mappings keyed by canonical mode."""
        self._rules: Dict[str, ModeRule] = {
            self._normalize_key(key): rule for key, rule in rules.items()
        }
        self._builders: Dict[str, type[ModeParams]] = {
            self._normalize_key(key): builder for key, builder in (builders or {}).items()
        }

    @classmethod
    def default(cls) -> "ModeRegistry":
        """Build the default registry used by experiment setup view models."""
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
        """Return all registered rules for iteration and diagnostics."""
        return self._rules.values()

    def rule_for(self, mode: str) -> ModeRule:
        """Return the mode rule for a UI or payload mode token."""
        key = self._normalize_key(mode)
        rule = self._rules.get(key)
        if not rule:
            raise ValueError(f"Unsupported mode: {mode}")
        return rule

    def label_for(self, mode: str) -> str:
        """Return a human-readable mode label, falling back to the input token."""
        try:
            return self.rule_for(mode).label
        except ValueError:
            return str(mode)

    def clipboard_attr_for(self, mode: str) -> str:
        """Return the ViewModel clipboard attribute name for the given mode."""
        return self.rule_for(mode).clipboard_attr

    def is_mode_field(self, mode: str, field_id: str) -> bool:
        """Check whether a field id belongs to the specified mode."""
        rule = self.rule_for(mode)
        return (
            field_id in rule.flags
            or field_id in rule.extras
            or any(field_id.startswith(prefix) for prefix in rule.prefixes)
        )

    def filter_fields(self, mode: str, fields: Mapping[str, str]) -> Dict[str, str]:
        """Extract mode-owned fields and force mode flags on for payload building."""
        rule = self.rule_for(mode)
        snapshot = {
            fid: val for fid, val in fields.items() if self.is_mode_field(mode, fid)
        }
        # Ensure downstream builders always see explicit "enabled" flags.
        for flag in rule.flags:
            snapshot[flag] = "1"
        return snapshot

    def builder_for(self, mode: str) -> Optional[type[ModeParams]]:
        """Return the mode parameter builder class, if one is registered."""
        return self._builders.get(self._normalize_key(mode))

    def backend_token(self, mode: str) -> str:
        """Normalize a UI mode label into the backend mode token."""
        return normalize_mode_name(mode)

    @staticmethod
    def _normalize_key(mode: str) -> str:
        """Normalize mapping keys so lookups are case-insensitive and trimmed."""
        return str(mode or "").strip().upper()


__all__ = ["ModeRegistry", "ModeRule"]
