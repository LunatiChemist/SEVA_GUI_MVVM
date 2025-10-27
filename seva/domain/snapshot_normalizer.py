from __future__ import annotations

"""Normalize adapter run snapshots into the domain GroupSnapshot aggregate."""

import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from .entities import (
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
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip()
    else:
        token = str(value).strip()
    return token or None


def _normalize_phase(value: Any) -> str:
    if isinstance(value, str):
        token = value.strip().lower()
        return token or "queued"
    if value is None:
        return "queued"
    token = str(value).strip().lower()
    return token or "queued"


def _coerce_progress(value: Any) -> Optional[ProgressPct]:
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
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return math.fsum(values) / len(values)


def normalize_status(raw: Mapping[str, Any] | GroupSnapshot | None) -> GroupSnapshot:
    """
    Convert heterogeneous adapter payloads into a strongly typed GroupSnapshot.

    Missing or malformed fields are interpreted defensively to keep polling resilient.
    """

    if isinstance(raw, GroupSnapshot):
        return raw

    if isinstance(raw, Mapping):
        payload: Mapping[str, Any] = raw
    else:
        payload = {}

    group_token = (
        _normalize_identifier(payload.get("group"))
        or _normalize_identifier(payload.get("group_id"))
        or _normalize_identifier(payload.get("run_group_id"))
        or "unknown-group"
    )
    group = GroupId(group_token)

    run_summaries: Dict[str, _RunSummary] = {}
    boxes: Dict[BoxId, BoxSnapshot] = {}
    has_boxes = False
    has_runs = False
    active_found = False

    raw_boxes = payload.get("boxes") if isinstance(payload, Mapping) else None
    if isinstance(raw_boxes, Mapping):
        for box_key, box_payload in raw_boxes.items():
            box_token = _normalize_identifier(box_key)
            if not box_token:
                continue
            box_id = BoxId(box_token)
            has_boxes = True

            runs_payload = []
            if isinstance(box_payload, Mapping):
                runs_payload = box_payload.get("runs") or []
            elif isinstance(box_payload, Sequence) and not isinstance(box_payload, (str, bytes)):
                runs_payload = box_payload

            progress_values: list[float] = []
            remaining_values: list[int] = []

            if isinstance(runs_payload, Sequence) and not isinstance(runs_payload, (str, bytes)):
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
                    error = _clean_error(run_entry.get("error") or run_entry.get("message"))
                    run_summaries[run_token] = _RunSummary(
                        phase=phase,
                        progress=progress,
                        remaining=remaining,
                        error=error,
                    )
                    has_runs = True
                    if phase not in TERMINAL_PHASES:
                        active_found = True

            avg_progress = _mean(progress_values)
            box_progress = ProgressPct(avg_progress) if avg_progress is not None else None
            max_remaining = max(remaining_values) if remaining_values else None
            box_remaining = Seconds(max_remaining) if max_remaining is not None else None
            boxes[box_id] = BoxSnapshot(box=box_id, progress=box_progress, remaining_s=box_remaining)

    wells_payload = payload.get("wells") if isinstance(payload, Mapping) else None
    runs: Dict[WellId, RunStatus] = {}
    if isinstance(wells_payload, Sequence) and not isinstance(wells_payload, (str, bytes)):
        for row in wells_payload:
            if isinstance(row, Mapping):
                wid_raw = row.get("well") or row.get("wid")
                state_raw = row.get("state") or row.get("status") or row.get("phase")
                progress_raw = row.get("progress") or row.get("progress_pct")
                remaining_raw = row.get("remaining") or row.get("remaining_s")
                error_raw = row.get("error") or row.get("message")
                run_id_raw = row.get("run_id") or row.get("subrun")
                cur_raw = row.get("current_mode") or row.get("mode")
                rem_raw = row.get("remaining_modes")
            elif isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
                row_list = list(row)
                if len(row_list) < 2:
                    continue
                wid_raw = row_list[0]
                state_raw = row_list[1]
                progress_raw = row_list[2] if len(row_list) > 2 else None
                if len(row_list) >= 6:
                    remaining_raw = row_list[3]
                    error_raw = row_list[4]
                    run_id_raw = row_list[5]
                elif len(row_list) >= 5:
                    remaining_raw = None
                    error_raw = row_list[3]
                    run_id_raw = row_list[4]
                else:
                    remaining_raw = None
                    error_raw = row_list[3] if len(row_list) > 3 else None
                    run_id_raw = row_list[4] if len(row_list) > 4 else None
            else:
                continue

            well_token = _normalize_identifier(wid_raw)
            run_token = _normalize_identifier(run_id_raw)
            if not well_token or not run_token:
                continue

            summary = run_summaries.get(run_token)
            phase = summary.phase if summary else _normalize_phase(state_raw)
            progress = summary.progress or _coerce_progress(progress_raw)
            remaining = summary.remaining or _coerce_seconds(remaining_raw)
            error = summary.error if summary and summary.error is not None else _clean_error(error_raw)

            # Wells bridge box-level runs to their domain identifier; we prefer server metrics.
            runs[WellId(well_token)] = RunStatus(
                run_id=RunId(run_token),
                phase=phase,
                progress=progress,
                remaining_s=remaining,
                error=error,
                current_mode=_normalize_identifier(cur_raw),
                remaining_modes=tuple(str(x).strip() for x in rem_raw) if isinstance(rem_raw, (list, tuple)) else tuple(),
            )

    if "all_done" in payload:
        all_done = bool(payload.get("all_done"))
    else:
        all_done = has_boxes and has_runs and not active_found

    return GroupSnapshot(group=group, runs=runs, boxes=boxes, all_done=all_done)


__all__ = ["normalize_status"]
