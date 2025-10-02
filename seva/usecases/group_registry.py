# seva/usecases/group_registry.py
from __future__ import annotations
from typing import Dict, Optional
from dataclasses import dataclass

# Simple in-memory store to share metadata between use cases.
# Future: move to StoragePort if persistence is needed.


@dataclass
class _BoxMeta:
    planned_duration_s: Optional[int] = None


# group_id -> box_id -> _BoxMeta
_GROUP_META: Dict[str, Dict[str, _BoxMeta]] = {}


def set_planned_duration(group_id: str, box_id: str, seconds: Optional[int]) -> None:
    meta = _GROUP_META.setdefault(group_id, {})
    box = meta.setdefault(box_id, _BoxMeta())
    box.planned_duration_s = seconds


def get_planned_duration(group_id: str, box_id: str) -> Optional[int]:
    meta = _GROUP_META.get(group_id, {})
    box = meta.get(box_id)
    return box.planned_duration_s if box else None
