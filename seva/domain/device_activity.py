from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SlotActivityEntry:
    well_id: str
    status: str


@dataclass(frozen=True)
class DeviceActivitySnapshot:
    entries: Tuple[SlotActivityEntry, ...]


__all__ = ["DeviceActivitySnapshot", "SlotActivityEntry"]
