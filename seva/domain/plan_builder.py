from __future__ import annotations

"""Helpers for converting UI/state snapshots into domain experiment plans."""

from datetime import datetime
from typing import Any, Dict, Mapping, Optional

from .entities import (
    ClientDateTime,
    ExperimentPlan,
    ModeName,
    PlanMeta,
    WellId,
    WellPlan,
    GroupId,
)
from .naming import make_group_id
from .params import CVParams, ModeParams

_MODE_BUILDERS: Dict[str, type[ModeParams]] = {
    "CV": CVParams,
    # TODO: register additional mode parameter builders when modes are implemented.
}


def build_meta(
    experiment: str,
    subdir: Optional[str],
    client_dt_local: datetime,
) -> PlanMeta:
    """Create plan metadata with a sanitized, naming-compliant group identifier."""

    localized = _ensure_local_timezone(client_dt_local)
    client_dt = ClientDateTime(localized)

    # Use a placeholder identifier to satisfy PlanMeta construction prior to naming.
    placeholder = PlanMeta(
        experiment=experiment,
        subdir=subdir,
        client_dt=client_dt,
        group_id=GroupId("pending"),
    )
    group_id = make_group_id(placeholder)
    return PlanMeta(
        experiment=placeholder.experiment,
        subdir=placeholder.subdir,
        client_dt=client_dt,
        group_id=group_id,
    )


def from_well_params(
    meta: PlanMeta,
    well_params_map: Mapping[str, Mapping[str, Any]],
    *,
    make_plot: bool,
    tia_gain: Optional[int],
    sampling_interval: Optional[float],
) -> ExperimentPlan:
    """Assemble an ExperimentPlan from persisted per-well form snapshots."""

    if not isinstance(well_params_map, Mapping) or not well_params_map:
        raise ValueError("from_well_params requires a non-empty mapping of well parameters.")

    well_plans: list[WellPlan] = []
    for well_id_raw in sorted(well_params_map):
        params_snapshot = well_params_map[well_id_raw]
        if not isinstance(params_snapshot, Mapping):
            raise TypeError(f"Well '{well_id_raw}' parameters must be a mapping.")

        mode_label = _derive_mode(params_snapshot)
        params_obj = _build_mode_params(mode_label, params_snapshot)

        # Mode assignment is the hand-off between view-model flags and domain objects.
        well_plans.append(
            WellPlan(
                well=WellId(str(well_id_raw)),
                mode=ModeName(mode_label),
                params=params_obj,
            )
        )

    return ExperimentPlan(
        meta=meta,
        wells=well_plans,
        make_plot=bool(make_plot),
        tia_gain=tia_gain,
        sampling_interval=sampling_interval,
    )


def _build_mode_params(mode_label: str, snapshot: Mapping[str, Any]) -> ModeParams:
    builder = _MODE_BUILDERS.get(mode_label)
    if builder is None:
        raise NotImplementedError(f"Mode '{mode_label}' is not supported yet.")

    # Converting the flat snapshot into a typed value object ensures downstream payloads serialize.
    return builder.from_form(snapshot)


def _derive_mode(snapshot: Mapping[str, Any]) -> str:
    flags = {
        "CV": snapshot.get("run_cv"),
        "DC": snapshot.get("run_dc"),
        "AC": snapshot.get("run_ac"),
        "LSV": snapshot.get("run_lsv"),
        "EIS": snapshot.get("run_eis"),
        "CDL": snapshot.get("run_cdl") or snapshot.get("eval_cdl"),
    }
    active = [mode for mode, value in flags.items() if _is_truthy(value)]
    if len(active) != 1:
        raise ValueError("Exactly one run_* flag must be enabled per well.")
    return active[0]


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on"}


def _ensure_local_timezone(candidate: datetime) -> datetime:
    if candidate.tzinfo is None or candidate.tzinfo.utcoffset(candidate) is None:
        local_zone = datetime.now().astimezone().tzinfo
        if local_zone is None:
            raise ValueError("Local timezone could not be determined for client timestamp.")
        return candidate.replace(tzinfo=local_zone)
    return candidate.astimezone()


__all__ = ["build_meta", "from_well_params"]
