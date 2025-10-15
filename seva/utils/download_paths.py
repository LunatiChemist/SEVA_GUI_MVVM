from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional

_PATH_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_-]+")
_CLIENT_DATETIME_RE = re.compile(r"[^0-9A-Za-zT_-]+")


def _value_or_none(value: Optional[str]) -> Optional[str]:
    """Return a trimmed string or None when the input is empty."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def sanitize_path_segment(raw: Optional[str]) -> Optional[str]:
    """Sanitize a path segment to keep only safe characters for local storage."""
    candidate = _value_or_none(raw)
    if candidate is None:
        return None
    sanitized = _PATH_SEGMENT_RE.sub("_", candidate)
    # Collapse duplicate separators so the segment stays compact.
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("_-")
    return sanitized or None


def sanitize_client_datetime(raw: Optional[str]) -> Optional[str]:
    """Normalize the client timestamp so it can be safely used as folder name."""
    candidate = _value_or_none(raw)
    if candidate is None:
        return None
    normalized = (
        candidate.replace(":", "-")
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(".", "-")
    )
    sanitized = _CLIENT_DATETIME_RE.sub("-", normalized)
    # Keep markers human-readable by squashing repeated underscores/dashes.
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized)
    sanitized = sanitized.strip("_-")
    return sanitized or None


def collect_box_runs(
    explicit: Dict[str, Iterable[str]], snapshot_boxes: Dict[str, Dict]
) -> Dict[str, List[str]]:
    """Gather run ids per box from explicit mapping or snapshot fallback."""
    collected: Dict[str, List[str]] = {
        box: [str(run_id) for run_id in runs if run_id]
        for box, runs in explicit.items()
        if runs
    }
    if collected:
        return collected
    fallback: Dict[str, List[str]] = {}
    for box, meta in snapshot_boxes.items():
        run_ids = [
            str(run.get("run_id"))
            for run in meta.get("runs") or []
            if run.get("run_id")
        ]
        if run_ids:
            fallback[box] = run_ids
    return fallback


def build_group_root(
    results_dir: Optional[str],
    experiment_name: Optional[str],
    client_datetime: Optional[str],
    *,
    subdir: Optional[str] = None,
    fallback_segment: Optional[str] = None,
) -> str:
    """Compose the absolute group root path based on the storage schema."""
    base = os.path.abspath(results_dir or ".")
    experiment_segment = sanitize_path_segment(experiment_name)
    subdir_segment = sanitize_path_segment(subdir)
    timestamp_segment = sanitize_client_datetime(client_datetime)

    # Only build the schema when both experiment and timestamp are known.
    if experiment_segment and timestamp_segment:
        segments = [base, experiment_segment]
        if subdir_segment:
            segments.append(subdir_segment)
        segments.append(timestamp_segment)
        return os.path.abspath(os.path.join(*segments))

    if fallback_segment:
        return os.path.abspath(os.path.join(base, str(fallback_segment)))

    return base


def build_zip_paths(
    results_dir: Optional[str], group_id: Optional[str], box_runs: Dict[str, Iterable[str]]
) -> List[str]:
    """Return absolute paths for downloaded ZIPs per box and run."""
    if not group_id:
        return []
    root = results_dir or "."
    group_root = os.path.abspath(os.path.join(root, str(group_id)))
    paths: List[str] = []
    for box in sorted(box_runs.keys()):
        runs = box_runs[box]
        for run_id in runs:
            if not run_id:
                continue
            path = os.path.join(group_root, box, f"{run_id}.zip")
            paths.append(os.path.abspath(path))
    return paths
