from __future__ import annotations

"""Central registry for mode normalization, labels, and clipboard rules."""

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple


@dataclass(frozen=True)
class ModeRule:
    """Definition of UI filtering rules for a single mode."""

    name: str
    prefixes: Tuple[str, ...]
    flags: Tuple[str, ...]
    extras: Tuple[str, ...]
    clipboard_attr: str


class ModeRegistry:
    """Placeholder registry for mode behavior."""

    def __init__(self, rules: Mapping[str, ModeRule] | None = None) -> None:
        self._rules: Dict[str, ModeRule] = dict(rules or {})

    def rules(self) -> Iterable[ModeRule]:
        return self._rules.values()


__all__ = ["ModeRegistry", "ModeRule"]
