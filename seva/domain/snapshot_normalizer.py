"""Normalize adapter run snapshots into the domain GroupSnapshot aggregate."""

from __future__ import annotations


import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from seva.domain.entities import (
    BoxId,
    BoxSnapshot,
    GroupId,
    GroupSnapshot,
    ProgressPct,
    RunId,
    RunStatus,
    Seconds,
    WellId,
)

TERMINAL_PHASES = {"done", "failed", "canceled", "cancelled"}


@dataclass
class _RunSummary:
    """Intermediate container with server metrics for a run."""

    phase: str
    progress: Optional[ProgressPct]
    remaining: Optional[Seconds]
    error: Optional[str]


def _normalize_identifier(value: Any) -> Optional[str]:
    """Normalize optional identifiers to trimmed tokens.
    
    Args:
        value (Any): Input provided by the caller.
    
    Returns:
        Optional[str]: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip()
    else:
        token = str(value).strip()
    return token or None


def _normalize_phase(value: Any) -> str:
    """Normalize run phase strings to canonical lowercase values.
    
    Args:
        value (Any): Input provided by the caller.
    
    Returns:
        str: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if isinstance(value, str):
        token = value.strip().lower()
        return token or "queued"
    if value is None:
        return "queued"
    token = str(value).strip().lower()
    return token or "queued"


def _coerce_progress(value: Any) -> Optional[ProgressPct]:
    """Convert dynamic progress values into ProgressPct entities.
    
    Args:
        value (Any): Input provided by the caller.
    
    Returns:
        Optional[ProgressPct]: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if value is None:
        return None
    if isinstance(value, ProgressPct):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        try:
            numeric = float(str(value).strip())
        except (TypeError, ValueError):
            return None
    if not math.isfinite(numeric):
        return None
    clamped = min(max(numeric, 0.0), 100.0)
    try:
        return ProgressPct(clamped)
    except ValueError:
        return None


def _coerce_seconds(value: Any) -> Optional[Seconds]:
    """Convert dynamic duration values into Seconds entities.
    
    Args:
        value (Any): Input provided by the caller.
    
    Returns:
        Optional[Seconds]: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if value is None:
        return None
    if isinstance(value, Seconds):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        try:
            numeric = float(str(value).strip())
        except (TypeError, ValueError):
            return None
    if not math.isfinite(numeric):
        return None
    rounded = int(round(numeric))
    if rounded < 0:
        return None
    try:
        return Seconds(rounded)
    except ValueError:
        return None


def _clean_error(value: Any) -> Optional[str]:
    """Normalize optional error text values.
    
    Args:
        value (Any): Input provided by the caller.
    
    Returns:
        Optional[str]: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mean(values: Sequence[float]) -> Optional[float]:
    """Compute the arithmetic mean for numeric samples.
    
    Args:
        values (Sequence[float]): Input provided by the caller.
    
    Returns:
        Optional[float]: Value returned to the caller.
    
    Raises:
        ValueError: Raised when normalized values violate domain constraints.
    """
    if not values:
        return None
    return math.fsum(values) / len(values)


def normalize_status(raw: Mapping[str, Any] | GroupSnapshot | None) -> GroupSnapshot:
    """Convert adapter payloads into a strongly typed GroupSnapshot."""
    if isinstance(raw, GroupSnapshot):
        return raw

    payload: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    group_token = str(payload.get("group") or "unknown-group").strip() or "unknown-group"
    group = GroupId(group_token)

    run_summaries: Dict[str, _RunSummary] = {}
    boxes: Dict[BoxId, BoxSnapshot] = {}
    active_found = False

    raw_boxes = payload.get("boxes") or {}
    if isinstance(raw_boxes, Mapping):
        for box_key, box_payload in raw_boxes.items():
            box_id = BoxId(str(box_key))
            runs_payload = (
                box_payload.get("runs") if isinstance(box_payload, Mapping) else box_payload
            )
            if not isinstance(runs_payload, Sequence) or isinstance(runs_payload, (str, bytes)):
                continue

            progress_values: list[float] = []
            remaining_values: list[int] = []

            for run_entry in runs_payload:
                if not isinstance(run_entry, Mapping):
                    continue
                run_token = _normalize_identifier(run_entry.get("run_id"))
                if not run_token:
                    continue
                phase = _normalize_phase(run_entry.get("status") or run_entry.get("phase"))
                progress = _coerce_progress(run_entry.get("progress_pct"))
                if progress is not None:
                    progress_values.append(progress.value)
                remaining = _coerce_seconds(run_entry.get("remaining_s"))
                if remaining is not None:
                    remaining_values.append(int(remaining.value))
                error = _clean_error(run_entry.get("error"))
                run_summaries[run_token] = _RunSummary(
                    phase=phase,
                    progress=progress,
                    remaining=remaining,
                    error=error,
                )
                if phase not in TERMINAL_PHASES:
                    active_found = True

            avg_progress = _mean(progress_values)
            box_progress = ProgressPct(avg_progress) if avg_progress is not None else None
            max_remaining = max(remaining_values) if remaining_values else None
            box_remaining = Seconds(max_remaining) if max_remaining is not None else None
            boxes[box_id] = BoxSnapshot(box=box_id, progress=box_progress, remaining_s=box_remaining)

    wells_payload = payload.get("wells") or []
    runs: Dict[WellId, RunStatus] = {}
    if isinstance(wells_payload, Sequence) and not isinstance(wells_payload, (str, bytes)):
        for row in wells_payload:
            if not isinstance(row, Mapping):
                continue
            well_token = _normalize_identifier(row.get("well"))
            run_token = _normalize_identifier(row.get("run_id"))
            if not well_token or not run_token:
                continue
            summary = run_summaries.get(run_token)
            phase = summary.phase if summary else _normalize_phase(row.get("phase") or row.get("status"))
            progress = summary.progress or _coerce_progress(row.get("progress_pct"))
            remaining = summary.remaining or _coerce_seconds(row.get("remaining_s"))
            error = summary.error if summary and summary.error is not None else _clean_error(row.get("error"))
            runs[WellId(well_token)] = RunStatus(
                run_id=RunId(run_token),
                phase=phase,
                progress=progress,
                remaining_s=remaining,
                error=error,
                current_mode=_normalize_identifier(row.get("current_mode")),
                remaining_modes=tuple(row.get("remaining_modes") or ()),
            )

    all_done = bool(payload.get("all_done")) if "all_done" in payload else (boxes and runs and not active_found)
    return GroupSnapshot(group=group, runs=runs, boxes=boxes, all_done=all_done)


__all__ = ["normalize_status"]
