"""Domain activity snapshot types for per-slot UI indicators.

These immutable objects are produced by use cases and consumed by view models
that render per-channel activity in the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SlotActivityEntry:
    """Immutable activity marker for one slot/well.
    
    Attributes:
        Instances are passed between use cases, adapters, and view models.
    """
    well_id: str
    status: str


@dataclass(frozen=True)
class DeviceActivitySnapshot:
    """Immutable activity snapshot for all slots of a device.
    
    Attributes:
        Instances are passed between use cases, adapters, and view models.
    """
    entries: Tuple[SlotActivityEntry, ...]


__all__ = ["DeviceActivitySnapshot", "SlotActivityEntry"]
