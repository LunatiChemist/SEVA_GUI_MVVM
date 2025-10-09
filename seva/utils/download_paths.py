from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional


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
