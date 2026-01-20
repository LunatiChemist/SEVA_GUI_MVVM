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


def _ensure_local_timezone(candidate: datetime) -> datetime:
    if candidate.tzinfo is None or candidate.tzinfo.utcoffset(candidate) is None:
        local_zone = datetime.now().astimezone().tzinfo
        if local_zone is None:
            raise ValueError("Local timezone could not be determined for client timestamp.")
        return candidate.replace(tzinfo=local_zone)
    return candidate.astimezone()


__all__ = ["build_meta"]
