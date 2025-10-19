from __future__ import annotations

"""Coordinator orchestrating the run flow without UI concerns."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, TYPE_CHECKING

from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    GroupSnapshot,
    PlanMeta,
    RunId,
    WellId,
)
from seva.domain.ports import DevicePort, JobPort, StoragePort
from seva.usecases.start_experiment_batch import WellValidationResult

if TYPE_CHECKING:  # pragma: no cover - type checking helper
    from seva.domain.settings import SettingsConfig

ValidationSummary = Sequence[WellValidationResult]
GroupRunIndex = Dict[WellId, RunId]
_UNSET = object()


def _noop(*_: object, **__: object) -> None:
    """Default no-op callback used for hooks."""


@dataclass(frozen=True)
class FlowTick:
    """Single decision unit returned by polling to guide scheduling."""

    event: str
    """Tick classification, e.g. 'tick', 'completed', or 'error'."""
    snapshot: Optional[GroupSnapshot] = None
    """Latest snapshot observed for the group when available."""
    next_delay_ms: Optional[int] = None
    """Optional delay hint for the next poll invocation."""
    error_msg: Optional[str] = None
    """Error information propagated when the flow transitions to failure."""


@dataclass
class GroupContext:
    """Mutable run context shared between flow steps."""

    group: GroupId
    """Identifier of the active run group."""
    meta: PlanMeta
    """Plan metadata captured when the run was prepared."""
    run_index: GroupRunIndex = field(default_factory=dict)
    """Mapping from well identifiers to backend run identifiers."""
    storage_meta: Dict[str, str] = field(default_factory=dict)
    """Plan-level storage metadata used for downloads."""


@dataclass
class FlowHooks:
    """Optional callbacks triggered on significant flow events."""

    on_started: Callable[[GroupContext], None] = _noop
    on_snapshot: Callable[[GroupSnapshot], None] = _noop
    on_completed: Callable[[Path], None] = _noop
    on_error: Callable[[str], None] = _noop
    on_validation_errors: Callable[[ValidationSummary], None] = _noop

    def __post_init__(self) -> None:
        self.on_started = self.on_started or _noop
        self.on_snapshot = self.on_snapshot or _noop
        self.on_completed = self.on_completed or _noop
        self.on_error = self.on_error or _noop
        self.on_validation_errors = self.on_validation_errors or _noop


class RunFlowCoordinator:
    """Coordinates the multi-step run lifecycle in discrete, UI-agnostic phases."""

    def __init__(
        self,
        job_port: JobPort,
        device_port: DevicePort,
        storage_port: StoragePort,
        uc_validate_start,
        uc_start,
        uc_poll,
        uc_download,
        settings: "SettingsConfig",
        hooks: Optional[FlowHooks] = None,
    ) -> None:
        """
        Initialize the coordinator with its collaborators.

        The injected use-case callables are kept untyped to avoid premature coupling
        while the flow contract is being extracted.
        """
        self.job_port = job_port
        self.device_port = device_port
        self.storage_port = storage_port
        self.uc_validate_start = uc_validate_start
        self.uc_start = uc_start
        self.uc_poll = uc_poll
        self.uc_download = uc_download
        self.settings = settings
        self.hooks = hooks or FlowHooks()
        self._active = False
        self._last_start_result: Optional[object] = None
        self._current_delay_ms: int = self._baseline_poll_interval()
        self._last_snapshot_signature: object = _UNSET
        self._completed_download_targets: Dict[str, Path] = {}

    def prepare_plan(
        self, vm_state: ExperimentPlan | Mapping[str, Any]
    ) -> ExperimentPlan | Mapping[str, Any]:
        """
        Transform the view-model state into a domain plan.

        For the initial skeleton the plan is passed through unchanged.
        """
        return vm_state

    def validate(
        self, plan: ExperimentPlan | Mapping[str, Any]
    ) -> ValidationSummary:
        """
        Run plan validation by delegating to the existing use-case.

        Returns the validation summary produced by the underlying use-case.
        """
        return self.uc_validate_start(plan)

    def start(
        self, plan: ExperimentPlan | Mapping[str, Any]
    ) -> GroupContext:
        """
        Start the experiment batch and allocate a fresh group context.

        Emits the `on_started` hook with the constructed context.
        """
        meta = self._resolve_meta(plan)
        start_result = self.uc_start(plan)
        group_identifier = meta.group_id
        start_group_value = getattr(start_result, "run_group_id", None)
        if start_group_value:
            group_identifier = GroupId(str(start_group_value))
        storage_meta = self._build_storage_meta(plan, meta)
        context = GroupContext(
            group=group_identifier,
            meta=meta,
            run_index={},
            storage_meta=storage_meta,
        )
        self._last_start_result = start_result
        self._active = True
        self._current_delay_ms = self._baseline_poll_interval()
        self._last_snapshot_signature = _UNSET
        self._completed_download_targets.pop(str(group_identifier), None)
        self.hooks.on_started(context)
        return context

    def poll_once(self, ctx: GroupContext) -> FlowTick:
        """
        Poll the backend once for the given group context.

        Emits the `on_snapshot` hook with the latest snapshot.
        """
        if not self._active:
            return FlowTick(event="stopped")

        try:
            snapshot = self.uc_poll(str(ctx.group))
        except Exception as exc:  # pragma: no cover - defensive guard
            self._active = False
            message = str(exc) or exc.__class__.__name__
            self.hooks.on_error(message)
            return FlowTick(event="error", error_msg=message)

        self.hooks.on_snapshot(snapshot)
        progress_changed = self._update_progress_state(snapshot)
        if snapshot and snapshot.all_done:
            self._active = False
            return FlowTick(event="completed", snapshot=snapshot)

        # Back off polling while no progress is reported to avoid busy looping.
        delay = self._compute_next_delay(progress_changed)
        return FlowTick(event="tick", snapshot=snapshot, next_delay_ms=delay)

    def on_completed(self, ctx: GroupContext, snapshot: GroupSnapshot) -> Path:
        """
        Handle flow completion for the specified context.

        Performs the optional auto-download and surfaces the extraction path
        through the completion hook.
        """
        if not snapshot or not snapshot.all_done:
            raise ValueError("Cannot complete flow without a finished snapshot.")

        group_key = str(ctx.group)
        cached = self._completed_download_targets.get(group_key)
        if cached is not None:
            return cached

        storage_meta = self._resolve_storage_meta(ctx)
        results_dir = storage_meta.get("results_dir") or self._resolve_results_dir()
        auto_download = self._auto_download_enabled()

        if auto_download:
            try:
                download_root = self.uc_download(
                    group_key,
                    results_dir,
                    storage_meta,
                    cleanup="archive",
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                message = str(exc) or exc.__class__.__name__
                self.hooks.on_error(message)
                raise
            path_obj = Path(download_root).resolve()
            self._completed_download_targets[group_key] = path_obj
            self.hooks.on_completed(path_obj)
            return path_obj

        fallback = Path(results_dir).resolve()
        self._completed_download_targets[group_key] = fallback
        return fallback

    def stop_polling(self) -> None:
        """
        Stop any further polling activity initiated by this coordinator.

        Future wiring will check `_active` before scheduling follow-up polls.
        """
        self._active = False
        self._current_delay_ms = self._baseline_poll_interval()
        self._last_snapshot_signature = _UNSET

    def last_start_result(self) -> Optional[object]:
        """Return the most recent start result for UI consumption when needed."""
        return self._last_start_result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _baseline_poll_interval(self) -> int:
        """Return the configured baseline poll interval in milliseconds."""
        raw = getattr(self.settings, "poll_interval_ms", 1000)
        try:
            delay = int(raw)
        except (TypeError, ValueError):
            delay = 1000
        delay = max(200, delay)
        return delay

    def _max_poll_backoff(self, baseline: int) -> int:
        """Return the effective backoff ceiling, honoring configuration defaults."""
        raw = getattr(self.settings, "poll_backoff_max_ms", None)
        try:
            limit = int(raw) if raw is not None else 5000
        except (TypeError, ValueError):
            limit = 5000
        if limit <= 0:
            limit = 5000
        return max(baseline, limit)

    def _compute_next_delay(self, progress_changed: bool) -> int:
        """Adjust the poll interval based on recent progress observations."""
        baseline = self._baseline_poll_interval()
        max_delay = self._max_poll_backoff(baseline)
        if progress_changed:
            self._current_delay_ms = baseline
            return self._current_delay_ms

        current = self._current_delay_ms or baseline
        next_delay = int(max(current * 1.5, current + 1))
        self._current_delay_ms = min(next_delay, max_delay)
        return self._current_delay_ms

    def _update_progress_state(
        self, snapshot: Optional[GroupSnapshot]
    ) -> bool:
        """Record the latest snapshot signature and report whether it changed."""
        signature = self._snapshot_signature(snapshot)
        previous = self._last_snapshot_signature
        self._last_snapshot_signature = signature
        if previous is _UNSET:
            return True
        return signature != previous

    def _snapshot_signature(
        self, snapshot: Optional[GroupSnapshot]
    ) -> Optional[tuple]:
        """Build a compact descriptor capturing phases and progress for diffing."""
        if not snapshot:
            return None

        run_entries = []
        for well, status in sorted(
            snapshot.runs.items(), key=lambda item: str(item[0])
        ):
            progress = (
                round(status.progress.value, 3)
                if getattr(status, "progress", None) is not None
                else None
            )
            remaining = (
                int(status.remaining_s.value)
                if getattr(status, "remaining_s", None) is not None
                else None
            )
            error = (status.error or "").strip() or None
            run_entries.append(
                (
                    str(status.run_id),
                    status.phase,
                    progress,
                    remaining,
                    error,
                )
            )

        box_entries = []
        for box, box_status in sorted(
            snapshot.boxes.items(), key=lambda item: str(item[0])
        ):
            progress = (
                round(box_status.progress.value, 3)
                if getattr(box_status, "progress", None) is not None
                else None
            )
            remaining = (
                int(box_status.remaining_s.value)
                if getattr(box_status, "remaining_s", None) is not None
                else None
            )
            box_entries.append((str(box), progress, remaining))

        return (
            snapshot.all_done,
            tuple(run_entries),
            tuple(box_entries),
        )

    def _resolve_storage_meta(self, ctx: GroupContext) -> Dict[str, str]:
        """Merge context metadata and settings into a storage payload."""
        meta: Dict[str, str] = dict(ctx.storage_meta or {})
        meta.setdefault("experiment", ctx.meta.experiment)
        if ctx.meta.subdir:
            meta.setdefault("subdir", ctx.meta.subdir)
        meta.setdefault("client_datetime", str(ctx.meta.client_dt))
        results_dir = meta.get("results_dir") or self._resolve_results_dir()
        meta["results_dir"] = results_dir
        return meta

    def _build_storage_meta(
        self,
        plan: ExperimentPlan | Mapping[str, Any],
        meta: PlanMeta,
    ) -> Dict[str, str]:
        """Extract storage metadata from the plan or fall back to defaults."""
        storage_meta: Dict[str, str] = {
            "experiment": meta.experiment,
            "client_datetime": str(meta.client_dt),
        }
        if meta.subdir:
            storage_meta["subdir"] = meta.subdir

        if isinstance(plan, Mapping):
            storage_section = plan.get("storage")
            if isinstance(storage_section, Mapping):
                experiment = storage_section.get("experiment_name")
                if isinstance(experiment, str) and experiment.strip():
                    storage_meta["experiment"] = experiment.strip()

                subdir = storage_section.get("subdir")
                if isinstance(subdir, str) and subdir.strip():
                    storage_meta["subdir"] = subdir.strip()

                client_dt = storage_section.get("client_datetime")
                if isinstance(client_dt, str) and client_dt.strip():
                    storage_meta["client_datetime"] = client_dt.strip()

                results_dir = storage_section.get("results_dir")
                if isinstance(results_dir, str) and results_dir.strip():
                    storage_meta["results_dir"] = results_dir.strip()

        results_dir = storage_meta.get("results_dir") or self._resolve_results_dir()
        storage_meta["results_dir"] = results_dir
        return storage_meta

    def _resolve_results_dir(self) -> str:
        """Best-effort resolution of the configured results directory."""
        raw = getattr(self.settings, "results_dir", ".")
        if isinstance(raw, str):
            cleaned = raw.strip()
            return cleaned or "."
        return "."

    def _auto_download_enabled(self) -> bool:
        """Interpret the auto-download toggle with a sensible default."""
        value = getattr(self.settings, "auto_download_on_complete", True)
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        return bool(value)

    def _resolve_meta(self, plan: ExperimentPlan | Mapping[str, Any]) -> PlanMeta:
        """Extract plan metadata regardless of whether the plan is a domain object or legacy dict."""
        if hasattr(plan, "meta"):
            meta = getattr(plan, "meta")
            if isinstance(meta, PlanMeta):
                return meta

        if isinstance(plan, Mapping):
            storage = plan.get("storage") or {}
            experiment = str(storage.get("experiment_name") or "").strip()
            if not experiment:
                experiment = "Experiment"

            subdir_raw = storage.get("subdir") if isinstance(storage, Mapping) else None
            subdir = str(subdir_raw).strip() or None

            client_dt = self._coerce_client_dt(storage.get("client_datetime"))
            group_identifier = str(plan.get("group_id") or "").strip() or "unknown-group"
            return PlanMeta(
                experiment=experiment,
                subdir=subdir,
                client_dt=client_dt,
                group_id=GroupId(group_identifier),
            )

        raise TypeError("Unsupported plan type supplied to RunFlowCoordinator.start.")

    def _coerce_client_dt(self, value: Any) -> ClientDateTime:
        """Convert persisted client datetime payloads into the domain value object."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return ClientDateTime(value)

        if isinstance(value, str):
            cleaned = value.replace(" ", "T").replace("_", "-")
            # Restore colon separators if the slug-style payload removed them.
            if "T" in cleaned and "-" in cleaned:
                date_part, time_part = cleaned.split("T", 1)
                time_part = time_part.replace("-", ":")
                cleaned = f"{date_part}T{time_part}"
            try:
                parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return ClientDateTime(parsed)
            except ValueError:
                pass

        return ClientDateTime(datetime.now(timezone.utc))


__all__ = [
    "FlowHooks",
    "FlowTick",
    "GroupContext",
    "RunFlowCoordinator",
]
