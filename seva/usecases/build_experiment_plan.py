"""Use case for assembling a domain ExperimentPlan from UI-provided inputs."""

from __future__ import annotations


from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

from seva.domain.entities import ExperimentPlan, ModeName, ModeParams, WellId, WellPlan
from seva.domain.plan_builder import build_meta
from seva.domain.ports import UseCaseError
from seva.domain.time_utils import parse_client_datetime
from seva.domain.modes import ModeRegistry


@dataclass(frozen=True)
class ModeSnapshot:
    """Snapshot of a single mode's flat parameters from the UI."""

    name: str
    params: Mapping[str, str]


@dataclass(frozen=True)
class WellSnapshot:
    """Snapshot of grouped mode parameters for one well."""

    well_id: str
    modes: Tuple[ModeSnapshot, ...]


@dataclass(frozen=True)
class ExperimentPlanRequest:
    """Inputs needed to build a domain ExperimentPlan."""

    experiment_name: str
    subdir: Optional[str]
    client_datetime_override: Optional[str]
    wells: Tuple[str, ...]
    well_snapshots: Tuple[WellSnapshot, ...]


@dataclass
class BuildExperimentPlan:
    """Build a domain ExperimentPlan from UI snapshots."""

    mode_registry: ModeRegistry = field(default_factory=ModeRegistry.default)

    def __call__(self, request: ExperimentPlanRequest) -> ExperimentPlan:
        """Validate UI snapshots and build a typed ``ExperimentPlan``.

        Args:
            request: Normalized payload assembled by presenter/viewmodel code.

        Returns:
            ExperimentPlan: Plan metadata plus per-well mode configuration.

        Side Effects:
            None. This method only transforms and validates in-memory objects.

        Call Chain:
            ``RunFlowPresenter.start_run`` -> ``BuildExperimentPlan.__call__`` ->
            ``StartExperimentBatch``.

        Usage:
            Called once per run-start action before any adapter I/O begins.

        Raises:
            UseCaseError: If required wells, modes, metadata, or parameters are
                missing or invalid.
        """
        wells = tuple(request.wells or ())
        if not wells:
            raise UseCaseError("NO_CONFIGURED_WELLS", "No configured wells to start.")

        experiment = str(request.experiment_name or "").strip()
        if not experiment:
            raise UseCaseError(
                "MISSING_EXPERIMENT",
                "Experiment name must be set in Settings.",
            )

        subdir = str(request.subdir).strip() if request.subdir is not None else None
        client_dt = parse_client_datetime(request.client_datetime_override)
        meta = build_meta(experiment=experiment, subdir=subdir, client_dt_local=client_dt)

        snapshot_map = {snapshot.well_id: snapshot for snapshot in request.well_snapshots}
        well_plans: list[WellPlan] = []

        for well_id in wells:
            token = str(well_id).strip()
            if not token:
                raise UseCaseError("INVALID_WELL", "Encountered empty well identifier.")
            snapshot = snapshot_map.get(token)
            if not snapshot:
                raise UseCaseError(
                    "MISSING_PARAMS",
                    f"No saved parameters found for configured well {token}.",
                )

            mode_names: list[ModeName] = []
            params_by_mode: Dict[ModeName, ModeParams] = {}
            for mode_snapshot in snapshot.modes:
                mode_token = str(mode_snapshot.name).strip()
                if not mode_token:
                    continue
                mode_names.append(ModeName(mode_token))

                # Prefer typed mode builders; gracefully handle legacy builders.
                builder = self.mode_registry.builder_for(mode_token) or ModeParams
                try:
                    params_obj = builder.from_form(mode_snapshot.params)
                except (NotImplementedError, AttributeError, TypeError):
                    params_obj = builder(flags=dict(mode_snapshot.params))  # type: ignore[arg-type]

                normalized = self.mode_registry.backend_token(mode_token)
                params_by_mode[ModeName(normalized)] = params_obj

            if not mode_names:
                raise UseCaseError(
                    "MISSING_MODES",
                    f"No active modes found for configured well {token}.",
                )

            well_plans.append(
                WellPlan(
                    well=WellId(token),
                    modes=mode_names,
                    params_by_mode=params_by_mode,
                )
            )

        if not well_plans:
            raise UseCaseError("EMPTY_PLAN", "No well plans could be built.")

        return ExperimentPlan(meta=meta, wells=well_plans)


__all__ = [
    "BuildExperimentPlan",
    "ExperimentPlanRequest",
    "ModeSnapshot",
    "WellSnapshot",
]
