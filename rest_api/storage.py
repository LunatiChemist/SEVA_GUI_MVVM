"""Filesystem naming and run-directory registry helpers for the REST API.

This module centralizes path normalization for experiment storage. `rest_api.app`
uses it while handling `/jobs`, `/runs/{run_id}/*`, and retention workflows.

The module maintains an in-memory mapping of `run_id -> run directory` and mirrors
it to `<RUNS_ROOT>/_run_paths.json` so the API can recover run locations across
process restarts.
"""

import json
import pathlib
import re
import threading
from typing import Dict, NamedTuple, Optional

from fastapi import HTTPException

PATH_SEGMENT_RE = re.compile(r"[^0-9A-Za-z_-]+")
CLIENT_DATETIME_RE = re.compile(r"[^0-9A-Za-zT_-]+")


class RunStorageInfo(NamedTuple):
    """Canonical storage-name parts derived from a start-job request.

    Attributes
    ----------
    experiment : str
        Sanitized experiment folder token.
    subdir : Optional[str]
        Optional sanitized grouping subfolder.
    timestamp_dir : str
        Filesystem-safe timestamp token used as final run directory name.
    timestamp_name : str
        Timestamp token variant used in filenames.
    filename_prefix : str
        Prefix used for generated plot/data files.
    """

    experiment: str
    subdir: Optional[str]
    timestamp_dir: str
    timestamp_name: str
    filename_prefix: str


RUN_DIRECTORY_LOCK = threading.Lock()
RUN_DIRECTORIES: Dict[str, pathlib.Path] = {}
_RUNS_ROOT: Optional[pathlib.Path] = None


def configure_runs_root(root: pathlib.Path) -> None:
    """Set the root output directory and warm the run-id cache.

    Parameters
    ----------
    root : pathlib.Path
        Base path where run directories are created.

    Side Effects
    ------------
    Clears and repopulates :data:`RUN_DIRECTORIES` from persisted index data.
    """
    global _RUNS_ROOT
    _RUNS_ROOT = root
    with RUN_DIRECTORY_LOCK:
        RUN_DIRECTORIES.clear()
        stored = _load_run_index_unlocked()
        for rid, rel in stored.items():
            candidate = root / pathlib.Path(rel)
            if candidate.is_dir():
                RUN_DIRECTORIES[rid] = candidate


def run_index_path() -> pathlib.Path:
    """Return `<RUNS_ROOT>/_run_paths.json`.

    Returns
    -------
    pathlib.Path
        Path to the JSON file that persists run-id directory mappings.
    """
    root = _require_root()
    return root / "_run_paths.json"


def value_or_none(value: Optional[str]) -> Optional[str]:
    """Normalize a possibly empty string to `None`.

    Parameters
    ----------
    value : Optional[str]
        Candidate value from request payloads.

    Returns
    -------
    Optional[str]
        Trimmed string when non-empty, otherwise `None`.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def sanitize_path_segment(raw: str, field_name: str) -> str:
    """Convert arbitrary text into a safe single path segment.

    Parameters
    ----------
    raw : str
        Raw string from the API request.
    field_name : str
        Field label used in client-facing error messages.

    Returns
    -------
    str
        Sanitized token containing only letters, numbers, `_`, and `-`.

    Raises
    ------
    HTTPException
        If the input is empty or collapses to an invalid token.
    """
    trimmed = (raw or "").strip()
    if not trimmed:
        raise HTTPException(400, f"{field_name} must not be empty")
    sanitized = PATH_SEGMENT_RE.sub("_", trimmed)
    sanitized = re.sub(r"_+", "_", sanitized)
    sanitized = re.sub(r"-+", "-", sanitized)
    sanitized = sanitized.strip("_-")
    if not sanitized:
        raise HTTPException(400, f"{field_name} is invalid")
    return sanitized


def sanitize_optional_segment(value: Optional[str]) -> Optional[str]:
    """Sanitize an optional folder segment.

    Parameters
    ----------
    value : Optional[str]
        Optional input from `subdir` or legacy `folder_name` fields.

    Returns
    -------
    Optional[str]
        Sanitized segment, or `None` when no meaningful value was provided.
    """
    candidate = value_or_none(value)
    if candidate is None:
        return None
    return sanitize_path_segment(candidate, "subdir")


def sanitize_client_datetime(raw: str) -> str:
    """Normalize a client timestamp into a filesystem-safe token.

    Parameters
    ----------
    raw : str
        Timestamp sent by GUI clients.

    Returns
    -------
    str
        Normalized token used in run folder and filename creation.

    Raises
    ------
    HTTPException
        If the timestamp is empty or becomes invalid after normalization.
    """
    trimmed = (raw or "").strip()
    if not trimmed:
        raise HTTPException(400, "client_datetime must not be empty")
    normalized = (
        trimmed.replace(":", "-")
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(".", "-")
    )
    sanitized = CLIENT_DATETIME_RE.sub("-", normalized)
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized)
    sanitized = sanitized.strip("_-")
    if not sanitized:
        raise HTTPException(400, "client_datetime is invalid")
    return sanitized


def record_run_directory(run_id: str, run_dir: pathlib.Path) -> None:
    """Persist a run-id to directory mapping in memory and on disk.

    Parameters
    ----------
    run_id : str
        Server-assigned run identifier.
    run_dir : pathlib.Path
        Absolute path to the run output directory.

    Side Effects
    ------------
    Updates :data:`RUN_DIRECTORIES` and `_run_paths.json` atomically.
    """
    try:
        rel = run_dir.relative_to(_require_root())
    except ValueError:
        rel = run_dir
    rel_str = rel.as_posix()
    with RUN_DIRECTORY_LOCK:
        RUN_DIRECTORIES[run_id] = run_dir
        data = _load_run_index_unlocked()
        data[run_id] = rel_str
        _write_run_index_unlocked(data)


def forget_run_directory(run_id: str) -> None:
    """Remove a persisted run mapping.

    Parameters
    ----------
    run_id : str
        Identifier to remove from memory and disk index.

    Side Effects
    ------------
    Deletes the run-id entry from memory and `_run_paths.json`.
    """
    with RUN_DIRECTORY_LOCK:
        RUN_DIRECTORIES.pop(run_id, None)
        data = _load_run_index_unlocked()
        if run_id in data:
            data.pop(run_id, None)
            if data:
                _write_run_index_unlocked(data)
            else:
                path = run_index_path()
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def resolve_run_directory(run_id: str) -> pathlib.Path:
    """Resolve a run output directory for artifact endpoints.

    Resolution order is:

    1. In-memory mapping in :data:`RUN_DIRECTORIES`
    2. Persisted JSON index (`_run_paths.json`)
    3. Legacy fallback `<RUNS_ROOT>/<run_id>`

    Parameters
    ----------
    run_id : str
        Identifier from `/runs/{run_id}/...` endpoints.

    Returns
    -------
    pathlib.Path
        Existing run directory path.

    Raises
    ------
    HTTPException
        HTTP 404 when no matching directory exists.
    """
    with RUN_DIRECTORY_LOCK:
        candidate = RUN_DIRECTORIES.get(run_id)
    if candidate and candidate.is_dir():
        return candidate

    data = _load_run_index_unlocked()
    rel = data.get(run_id)
    if rel:
        run_dir = _require_root() / pathlib.Path(rel)
        if run_dir.is_dir():
            with RUN_DIRECTORY_LOCK:
                RUN_DIRECTORIES[run_id] = run_dir
            return run_dir

    fallback = _require_root() / run_id
    if fallback.is_dir():
        with RUN_DIRECTORY_LOCK:
            RUN_DIRECTORIES[run_id] = fallback
        return fallback

    raise HTTPException(404, "Run not found")


def _require_root() -> pathlib.Path:
    """Return configured runs root.

    Returns
    -------
    pathlib.Path
        Current configured runs root.

    Raises
    ------
    RuntimeError
        If :func:`configure_runs_root` was not called yet.
    """
    if _RUNS_ROOT is None:
        raise RuntimeError("RUNS_ROOT has not been configured yet")
    return _RUNS_ROOT


def _load_run_index_unlocked() -> Dict[str, str]:
    """Load run mappings from disk without acquiring the lock.

    Returns
    -------
    Dict[str, str]
        Mapping of run id to relative directory path. Invalid or unreadable
        content degrades to an empty mapping.
    """
    try:
        raw = run_index_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return {
        run_id: rel
        for run_id, rel in data.items()
        if isinstance(run_id, str) and isinstance(rel, str)
    }


def _write_run_index_unlocked(data: Dict[str, str]) -> None:
    """Write the run index atomically without acquiring the lock.

    Parameters
    ----------
    data : Dict[str, str]
        Mapping to persist.

    Side Effects
    ------------
    Writes a temporary file and atomically replaces `_run_paths.json`.
    """
    path = run_index_path()
    tmp = path.with_suffix(".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
