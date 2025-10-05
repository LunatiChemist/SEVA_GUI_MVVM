from __future__ import annotations
from typing import Dict, Optional
from dataclasses import dataclass

# Simple in-memory store to share metadata between use cases.
# Future: move to StoragePort if persistence is needed.


@dataclass
class _RunMeta:
    planned_duration_s: Optional[int] = None
    mode: Optional[str] = None  # optional, could help diagnostics later


# group_id -> run_id -> _RunMeta
_GROUP_META: Dict[str, Dict[str, _RunMeta]] = {}


def set_planned_duration(
    group_id: str, run_id: str, seconds: Optional[int], mode: Optional[str] = None
) -> None:
    meta = _GROUP_META.setdefault(group_id, {})
    run = meta.setdefault(run_id, _RunMeta())
    run.planned_duration_s = seconds
    if mode:
        run.mode = mode


def get_planned_duration(group_id: str, run_id: str) -> Optional[int]:
    meta = _GROUP_META.get(group_id, {})
    run = meta.get(run_id)
    return run.planned_duration_s if run else None
