from __future__ import annotations

"""Domain value objects and aggregates shared across adapters, use-cases, and view models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class GroupId:
    """Normalized identifier that ties together plans and snapshots across the system."""

    value: str
    """Sanitized identifier string safe for persistence, URLs, and file-system paths."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("GroupId must be a non-empty string.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RunId:
    """Identifier exposed by the backend for an individual run."""

    value: str
    """Backend-provided identifier string for the run, preserved verbatim."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("RunId must be a non-empty string.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class WellId:
    """Identifier for a plate well within a plan or snapshot."""

    value: str
    """Domain identifier string for a well, typically in A1 notation."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("WellId must be a non-empty string.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BoxId:
    """Identifier for a potentiostat box or device enclosure."""

    value: str
    """Stable identifier string used to address a specific box."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("BoxId must be a non-empty string.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ModeName:
    """Logical name of the electrochemical mode executed for a well."""

    value: str
    """Name of the mode as understood by both the UI and the backend."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("ModeName must be a non-empty string.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ClientDateTime:
    """Client-side timestamp captured when a plan is created."""

    value: datetime
    """Timezone-aware timestamp representing when the client issued the plan."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime):
            raise TypeError("ClientDateTime requires a datetime instance.")
        if self.value.tzinfo is None or self.value.tzinfo.utcoffset(self.value) is None:
            raise ValueError("ClientDateTime must be timezone-aware.")

    def __str__(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True)
class ServerDateTime:
    """Timestamp returned by the backend or hardware controller."""

    value: datetime
    """Timezone-aware timestamp reported by the backend for status updates."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime):
            raise TypeError("ServerDateTime requires a datetime instance.")
        if self.value.tzinfo is None or self.value.tzinfo.utcoffset(self.value) is None:
            raise ValueError("ServerDateTime must be timezone-aware.")

    def __str__(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True)
class ProgressPct:
    """Percentage-based progress indicator confined to 0–100 inclusive."""

    value: float
    """Progress value in percent, clamped to the inclusive range [0.0, 100.0]."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, (float, int)):
            raise TypeError("ProgressPct expects a numeric percent value.")
        numeric = float(self.value)
        if numeric < 0.0 or numeric > 100.0:
            raise ValueError("ProgressPct must be within the inclusive range [0, 100].")
        object.__setattr__(self, "value", numeric)

    def __float__(self) -> float:
        return self.value

    def __str__(self) -> str:
        return f"{self.value:.2f}%"


@dataclass(frozen=True)
class Seconds:
    """Amount of elapsed or remaining time expressed in whole seconds."""

    value: int
    """Non-negative number of seconds representing a duration measurement."""

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)):
            raise TypeError("Seconds expects an integer number of seconds.")
        numeric = int(self.value)
        if numeric < 0:
            raise ValueError("Seconds cannot be negative.")
        object.__setattr__(self, "value", numeric)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return f"{self.value}s"


@dataclass(frozen=True)
class ModeParams:
    """Base container for electrochemistry mode configuration."""

    flags: Mapping[str, Any]
    """Mode toggle flags derived from the mode definition."""

    def __post_init__(self) -> None:
        mapping = dict(self.flags or {})
        object.__setattr__(self, "flags", mapping)

    def get_enabled(self) -> Iterable[str]:
        """Return an iterable of flag names that are enabled."""

        return (name for name, enabled in self.flags.items() if enabled)

    @classmethod
    def from_form(cls, form: Mapping[str, Any]) -> "ModeParams":
        """Construct a params object from a flat form snapshot."""

        raise NotImplementedError("ModeParams subclasses must implement from_form().")

    def to_payload(self) -> Dict[str, Any]:
        """Serialize the parameters into the REST API payload schema."""

        raise NotImplementedError("ModeParams subclasses must implement to_payload().")


@dataclass(frozen=True)
class PlanMeta:
    """Describes the plan-level metadata shared across all wells."""

    experiment: str
    """Human-readable experiment name supplied by the operator."""
    subdir: Optional[str]
    """Optional subdirectory that further scopes exported results."""
    client_dt: ClientDateTime
    """Client-side timestamp capturing when the plan was assembled."""
    group_id: GroupId
    """Deterministic group identifier allocated for this plan."""
    make_plot: Optional[bool] = False
    """Whether the backend should generate plots for each run."""
    tia_gain: Optional[int] = None
    """Optional transimpedance amplifier gain override."""
    sampling_interval: Optional[float] = None
    """Optional sampling interval override supplied by the client."""

    def __post_init__(self) -> None:
        experiment = self.experiment.strip()
        if not experiment:
            raise ValueError("PlanMeta.experiment must not be blank.")
        object.__setattr__(self, "experiment", experiment)

        if self.subdir is not None:
            cleaned = self.subdir.strip()
            object.__setattr__(self, "subdir", cleaned or None)


@dataclass(frozen=True)
class WellPlan:
    """Plan for an individual well including its mode and configuration."""
    well: WellId
    modes: List[ModeName]
    params_by_mode: Dict[ModeName,ModeParams]


@dataclass(frozen=True)
class ExperimentPlan:
    """Aggregate capturing the entire experiment plan before submission."""
    meta: PlanMeta
    """Shared metadata applied to all well plans in the batch."""
    wells: List[WellPlan]

    def __post_init__(self) -> None:
        if not self.wells:
            raise ValueError("ExperimentPlan.wells must contain at least one WellPlan.")
        if not all(isinstance(plan, WellPlan) for plan in self.wells):
            raise TypeError("ExperimentPlan.wells must only contain WellPlan instances.")

        # object.__setattr__(self, "make_plot", bool(self.make_plot))


@dataclass(frozen=True)
class RunStatus:
    """Lifecycle information for a single run reported by polling."""

    run_id: RunId
    """Identifier assigned to the run by the backend."""
    phase: str
    """Current lifecycle phase label reported by the backend (e.g. queued, running, done)."""
    progress: Optional[ProgressPct] = None
    """Latest known progress percentage if provided by the backend."""
    remaining_s: Optional[Seconds] = None
    """Estimated number of seconds left until completion, if supplied."""
    error: Optional[str] = None
    """User-facing error message when the run fails, else None."""

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or not self.phase.strip():
            raise ValueError("RunStatus.phase must be a non-empty string.")
        object.__setattr__(self, "phase", self.phase.strip())


@dataclass(frozen=True)
class BoxSnapshot:
    """Snapshot describing aggregate progress for a single box."""

    box: BoxId
    """Identifier of the box the snapshot was generated for."""
    progress: Optional[ProgressPct] = None
    """Aggregated progress percentage across runs on this box, if present."""
    remaining_s: Optional[Seconds] = None
    """Estimated remaining time in seconds until all runs on this box finish."""


@dataclass(frozen=True)
class GroupSnapshot:
    """Combined snapshot of all runs and boxes belonging to a plan group."""

    group: GroupId
    """Group identifier that the snapshot refers to."""
    runs: Dict[WellId, RunStatus]
    """Per-well mapping that surfaces the latest run status for each scheduled well."""
    boxes: Dict[BoxId, BoxSnapshot]
    """Per-box mapping summarizing aggregate progress state for each involved box."""
    all_done: bool = False
    """Flag indicating whether every run in the group has finished successfully."""

    def __post_init__(self) -> None:
        self._validate_mapping("runs", self.runs, WellId, RunStatus)
        self._validate_mapping("boxes", self.boxes, BoxId, BoxSnapshot)

    @staticmethod
    def _validate_mapping(
        attr_name: str,
        mapping: Mapping,
        expected_key: type,
        expected_value: type,
    ) -> None:
        if not isinstance(mapping, Mapping):
            raise TypeError(f"GroupSnapshot.{attr_name} must be a mapping.")
        for key, value in mapping.items():
            if not isinstance(key, expected_key):
                raise TypeError(
                    f"GroupSnapshot.{attr_name} keys must be {expected_key.__name__} instances."
                )
            if not isinstance(value, expected_value):
                raise TypeError(
                    f"GroupSnapshot.{attr_name} values must be {expected_value.__name__} instances."
                )


__all__ = [
    "BoxId",
    "BoxSnapshot",
    "ClientDateTime",
    "ExperimentPlan",
    "GroupId",
    "GroupSnapshot",
    "ModeName",
    "ModeParams",
    "PlanMeta",
    "ProgressPct",
    "RunId",
    "RunStatus",
    "Seconds",
    "ServerDateTime",
    "WellId",
    "WellPlan",
]
