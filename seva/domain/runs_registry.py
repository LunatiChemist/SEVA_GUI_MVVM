from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TYPE_CHECKING

from seva.domain.entities import GroupSnapshot

if TYPE_CHECKING:  # pragma: no cover - type checking helper
    from seva.usecases.run_flow_coordinator import (
        FlowHooks,
        GroupContext,
        RunFlowCoordinator,
    )


@dataclass
class DownloadInfo:
    """Tracks download completion metadata for a run group."""

    done: bool = False
    path: Optional[str] = None


@dataclass
class RunEntry:
    """Persisted registry entry for a run group."""

    group_id: str
    name: Optional[str]
    boxes: List[str]
    runs_by_box: Dict[str, List[str]]
    created_at: str
    plan_meta: Dict[str, Any]
    storage_meta: Dict[str, str]
    status: str = "running"
    download: DownloadInfo = field(default_factory=DownloadInfo)
    last_snapshot: Optional[Dict[str, Any]] = None


class RunsRegistry:
    """
    Singleton registry that persists metadata for all run groups.

    The registry keeps lightweight metadata for UI presentation, persists
    group status so the client can re-attach on startup, and manages the
    runtime wiring between group identifiers and their coordinators.
    """

    _instance: Optional["RunsRegistry"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "RunsRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        self._log = logging.getLogger(__name__)
        self._entries: Dict[str, RunEntry] = {}
        self._coordinators: Dict[str, "RunFlowCoordinator"] = {}
        self._contexts: Dict[str, "GroupContext"] = {}
        self._hooks_factory: Optional[Callable[[str], "FlowHooks"]] = None
        self._coordinator_factory: Optional[
            Callable[
                [str, Dict[str, Any], Dict[str, str], "FlowHooks"],
                "RunFlowCoordinator",
            ]
        ] = None
        self._store_path: Path = self._default_store_path()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    def configure(
        self,
        *,
        store_path: Optional[Path] = None,
        hooks_factory: Optional[Callable[[str], "FlowHooks"]] = None,
        coordinator_factory: Optional[
            Callable[
                [str, Dict[str, Any], Dict[str, str], "FlowHooks"],
                "RunFlowCoordinator",
            ]
        ] = None,
    ) -> None:
        if store_path is not None:
            self._store_path = store_path
        if hooks_factory is not None:
            self._hooks_factory = hooks_factory
        if coordinator_factory is not None:
            self._coordinator_factory = coordinator_factory

    # ------------------------------------------------------------------ #
    # Runtime wiring helpers
    # ------------------------------------------------------------------ #
    def register_runtime(
        self,
        group_id: str,
        coordinator: "RunFlowCoordinator",
        context: "GroupContext",
    ) -> None:
        """Register the runtime coordinator/context for an active group."""
        self._coordinators[group_id] = coordinator
        self._contexts[group_id] = context

    def unregister_runtime(self, group_id: str) -> None:
        """Drop runtime pointers when a run finishes or is removed."""
        self._coordinators.pop(group_id, None)
        self._contexts.pop(group_id, None)

    def coordinator_for(self, group_id: str) -> Optional["RunFlowCoordinator"]:
        return self._coordinators.get(group_id)

    def context_for(self, group_id: str) -> Optional["GroupContext"]:
        return self._contexts.get(group_id)

    def start_tracking(self, group_id: str) -> Optional["GroupContext"]:
        """
        Ensure the specified group is tracked by a coordinator instance.

        When the registry already has a runtime coordinator the call is a no-op.
        Otherwise the configured factories are used to rebuild the runtime state.
        """
        if group_id in self._coordinators:
            return self._contexts.get(group_id)

        entry = self._entries.get(group_id)
        if not entry:
            return None

        if not self._hooks_factory or not self._coordinator_factory:
            raise RuntimeError("RunsRegistry is not configured with factories.")

        hooks = self._hooks_factory(group_id)
        coordinator = self._coordinator_factory(
            group_id, entry.plan_meta, entry.storage_meta, hooks
        )
        if not hasattr(coordinator, "attach"):
            raise AttributeError("RunFlowCoordinator requires an attach() method.")

        attach = getattr(coordinator, "attach")
        context = attach(  # type: ignore[misc]
            group_id=group_id,
            plan_meta=entry.plan_meta,
            storage_meta=entry.storage_meta,
            hooks=hooks,
        )
        if context is None:
            raise RuntimeError("RunFlowCoordinator.attach() returned None.")

        self._coordinators[group_id] = coordinator
        self._contexts[group_id] = context
        return context

    # ------------------------------------------------------------------ #
    # Registry CRUD API
    # ------------------------------------------------------------------ #
    def add(
        self,
        *,
        group_id: str,
        name: Optional[str],
        boxes: Iterable[str],
        runs_by_box: Dict[str, Iterable[str]],
        plan_meta: Dict[str, Any],
        storage_meta: Dict[str, str],
        created_at_iso: Optional[str] = None,
    ) -> None:
        created = created_at_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = RunEntry(
            group_id=group_id,
            name=name,
            boxes=[str(box) for box in boxes],
            runs_by_box={str(box): [str(run) for run in runs] for box, runs in runs_by_box.items()},
            created_at=created,
            plan_meta=dict(plan_meta or {}),
            storage_meta=dict(storage_meta or {}),
            status="running",
        )
        self._entries[group_id] = entry
        self._persist()

    def update_snapshot(self, group_id: str, snapshot: Any) -> None:
        entry = self._entries.get(group_id)
        if not entry:
            return
        entry.last_snapshot = self._serialize_snapshot(snapshot)

    def mark_done(self, group_id: str, download_path: Optional[str]) -> None:
        entry = self._entries.get(group_id)
        if not entry:
            return
        entry.status = "done"
        entry.download = DownloadInfo(done=True, path=download_path)
        self.unregister_runtime(group_id)
        self._persist()

    def mark_cancelled(self, group_id: str) -> None:
        entry = self._entries.get(group_id)
        if not entry:
            return
        entry.status = "cancelled"
        self.unregister_runtime(group_id)
        self._persist()

    def mark_error(self, group_id: str, message: Optional[str] = None) -> None:
        entry = self._entries.get(group_id)
        if not entry:
            return
        entry.status = "error"
        if message:
            entry.plan_meta.setdefault("last_error", str(message))
        self.unregister_runtime(group_id)
        self._persist()

    def remove(self, group_id: str) -> None:
        # Safety: do not remove active groups; require cancel/done first
        if group_id in self.active_groups():
            coord = self._coordinators.get(group_id)
            if coord and hasattr(coord, "stop_polling"):
                try:
                    coord.stop_polling()  # type: ignore[attr-defined]
                except Exception:
                    pass
            return

        entry = self._entries.pop(group_id, None)
        if entry is None:
            return
        coordinator = self._coordinators.pop(group_id, None)
        self._contexts.pop(group_id, None)
        if coordinator and hasattr(coordinator, "stop_polling"):
            try:
                coordinator.stop_polling()  # type: ignore[attr-defined]
            except Exception:
                pass
        self._persist()

    def get(self, group_id: str) -> Optional[RunEntry]:
        return self._entries.get(group_id)

    def all_entries(self) -> List[RunEntry]:
        return list(self._entries.values())

    def active_groups(self) -> List[str]:
        return [
            group_id
            for group_id, entry in self._entries.items()
            if entry.status in {"running", "pending"}
        ]

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        self._entries.clear()
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
        except Exception:
            return

        entries = data.get("entries") or []
        failed = 0
        for payload in entries:
            try:
                download_payload = payload.get("download") or {}
                entry = RunEntry(
                    group_id=payload["group_id"],
                    name=payload.get("name"),
                    boxes=[str(box) for box in payload.get("boxes", [])],
                    runs_by_box={
                        str(box): [str(run) for run in runs]
                        for box, runs in (payload.get("runs_by_box") or {}).items()
                    },
                    created_at=payload.get("created_at") or "",
                    plan_meta=dict(payload.get("plan_meta") or {}),
                    storage_meta=dict(payload.get("storage_meta") or {}),
                    status=payload.get("status") or "running",
                    download=DownloadInfo(
                        done=bool(download_payload.get("done")),
                        path=download_payload.get("path"),
                    ),
                    last_snapshot=payload.get("last_snapshot"),
                )
            except Exception:
                failed += 1
                continue
            self._entries[entry.group_id] = entry
        if failed:
            self._log.warning("RunsRegistry load skipped %d invalid entries.", failed)

    def save(self) -> None:
        self._persist()

    # ------------------------------------------------------------------ #
    # Internal utilities
    # ------------------------------------------------------------------ #
    def _serialize_snapshot(self, snapshot: Any) -> Optional[Dict[str, Any]]:
        if snapshot is None:
            return None
        if isinstance(snapshot, dict):
            return snapshot
        if isinstance(snapshot, GroupSnapshot):
            return {
                "group": str(snapshot.group),
                "runs": {
                    str(well): {
                        "run_id": str(status.run_id),
                        "phase": status.phase,
                        "progress": getattr(status.progress, "value", None),
                        "remaining_s": getattr(status.remaining_s, "value", None),
                        "error": status.error,
                    }
                    for well, status in snapshot.runs.items()
                },
                "boxes": {
                    str(box): {
                        "progress": getattr(box_status.progress, "value", None),
                        "remaining_s": getattr(box_status.remaining_s, "value", None),
                    }
                    for box, box_status in snapshot.boxes.items()
                },
                "all_done": bool(snapshot.all_done),
            }
        try:
            return json.loads(json.dumps(snapshot))
        except Exception:
            return None

    def _persist(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [
                {
                    **asdict(entry),
                    "boxes": list(entry.boxes),
                    "runs_by_box": {
                        box: list(runs) for box, runs in entry.runs_by_box.items()
                    },
                }
                for entry in self._entries.values()
            ]
        }
        self._store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _default_store_path() -> Path:
        return Path.home() / ".seva" / "runs_registry.json"


__all__ = [
    "DownloadInfo",
    "RunEntry",
    "RunsRegistry",
]
