from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Type
from uuid import uuid4

from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    ModeName,
    PlanMeta,
    WellId,
    WellPlan,
)
from seva.domain.params import CVParams, ModeParams as DomainModeParams
from seva.domain.ports import (
    BoxId,
    JobPort,
    RunGroupId,
    UseCaseError,
    WellId,
)

# ---- Mode parameter mapping (legacy compat) ----

_MODE_PARAM_BUILDERS: Dict[str, Type[DomainModeParams]] = {
    "CV": CVParams,
    # TODO(mode:EIS): register once mode parameter objects exist.
    # TODO(mode:CDL): register once mode parameter objects exist.
    # TODO(mode:DC): register once mode parameter objects exist.
    # TODO(mode:AC): register once mode parameter objects exist.
}


def map_params(mode: str, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply mode-specific parameter mapping using domain value objects."""

    params_cls = _MODE_PARAM_BUILDERS.get((mode or "").upper())
    if not params_cls:
        # TODO: replace with strict mapping once the mode payload is defined.
        return {
            k: v
            for k, v in snapshot.items()
            if k
            not in (
                "run_cv",
                "run_eis",
                "run_cdl",
                "run_dc",
                "run_ac",
                "eval_cdl",
            )
        }

    params = params_cls.from_form(snapshot)
    return params.to_payload()

def _parse_client_datetime(raw: Any) -> datetime:
    """Parse a client datetime value into a timezone-aware datetime."""
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw or "").strip()
        if not text:
            dt = datetime.now(timezone.utc)
        else:
            normalized = text
            suffix_z = False
            if normalized.endswith("Z"):
                suffix_z = True
                normalized = normalized[:-1]
            try:
                candidate = normalized + ("+00:00" if suffix_z else "")
                dt = datetime.fromisoformat(candidate)
            except ValueError:
                try:
                    dt = datetime.strptime(normalized, "%Y-%m-%dT%H-%M-%S")
                    dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    dt = datetime.now(timezone.utc)
            else:
                if suffix_z and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.replace(microsecond=0)

def _derive_mode(snapshot: Mapping[str, Any]) -> str:
    """Determine the selected mode from run_* flags in the snapshot."""
    flags = {
        "CV": snapshot.get("run_cv"),
        "DC": snapshot.get("run_dc"),
        "AC": snapshot.get("run_ac"),
        "LSV": snapshot.get("run_lsv"),
        "EIS": snapshot.get("run_eis"),
        "CDL": snapshot.get("run_cdl") or snapshot.get("eval_cdl"),
    }
    picked = [
        mode
        for mode, value in flags.items()
        if str(value).strip().lower() in ("1", "true", "yes", "on")
    ]
    if len(picked) != 1:
        raise ValueError(f"Exactly one run_* flag must be set (got {picked or 'none'}).")
    return picked[0]

def build_experiment_plan(plan_dict: Mapping[str, Any]) -> ExperimentPlan:
    """Convert a legacy plan mapping into a typed ExperimentPlan."""
    selection_raw = plan_dict.get("selection") or []
    selection = [str(item) for item in selection_raw if item is not None]
    if not selection:
        raise ValueError("Start plan has no wells (selection is empty).")

    raw_params = plan_dict.get("well_params_map") or {}
    if not isinstance(raw_params, Mapping) or not raw_params:
        raise ValueError("Start plan has no per-well parameters (well_params_map missing).")

    storage = plan_dict.get("storage") or {}
    if not isinstance(storage, Mapping):
        storage = {}
    experiment_name = str(storage.get("experiment_name") or "").strip()
    if not experiment_name:
        raise UseCaseError("METADATA_MISSING", "Experiment name must be configured.")
    subdir = str(storage.get("subdir") or "").strip() or None
    client_dt = _parse_client_datetime(storage.get("client_datetime"))

    group_id_raw = plan_dict.get("group_id") or storage.get("group_id")
    group_id_value = str(group_id_raw).strip() if group_id_raw else str(uuid4())

    wells: List[WellPlan] = []
    for wid in selection:
        snapshot = raw_params.get(wid) or raw_params.get(WellId(wid))
        if not isinstance(snapshot, Mapping):
            raise ValueError(f"No saved parameters for well '{wid}'")
        mode_label = _derive_mode(snapshot)
        params_cls = _MODE_PARAM_BUILDERS.get(mode_label.upper())
        if not params_cls:
            raise ValueError(f"Unsupported mode '{mode_label}' for well '{wid}'.")
        params_obj = params_cls.from_form(snapshot)
        wells.append(
            WellPlan(
                well=WellId(wid),
                mode=ModeName(mode_label),
                params=params_obj,
            )
        )

    meta = PlanMeta(
        experiment=experiment_name,
        subdir=subdir,
        client_dt=ClientDateTime(client_dt),
        group_id=GroupId(group_id_value),
    )

    return ExperimentPlan(
        meta=meta,
        wells=wells,
        make_plot=bool(plan_dict.get("make_plot", True)),
        tia_gain=plan_dict.get("tia_gain"),
        sampling_interval=plan_dict.get("sampling_interval"),
    )

@dataclass
class WellValidationResult:
    """Structured summary for per-well validation feedback."""

    well_id: WellId
    box_id: BoxId
    mode: str
    ok: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]


@dataclass
class StartBatchResult:
    """Aggregate outcome for a batch start attempt."""

    run_group_id: Optional[RunGroupId]
    per_box_runs: Dict[BoxId, List[str]]
    started_wells: List[str]


@dataclass
class StartExperimentBatch:
    job_port: JobPort

    def __call__(self, plan: ExperimentPlan | Mapping[str, Any]) -> StartBatchResult:
        """Build one job per well from a validated experiment plan and submit the batch."""
        try:
            if isinstance(plan, Mapping):
                plan = build_experiment_plan(plan)
            elif not isinstance(plan, ExperimentPlan):
                raise TypeError("StartExperimentBatch requires an ExperimentPlan instance.")

            meta = plan.meta
            client_dt_value = meta.client_dt.value.astimezone(timezone.utc)
            client_dt_clean = client_dt_value.replace(microsecond=0).isoformat()
            if client_dt_clean.endswith("+00:00"):
                client_dt_clean = client_dt_clean.replace("+00:00", "Z")
            storage_payload = {
                "experiment_name": meta.experiment,
                "subdir": meta.subdir or None,
                "client_datetime": client_dt_clean,
            }

            group_id: RunGroupId = str(meta.group_id)
            jobs: List[Dict[str, Any]] = []
            started_wells: List[str] = []

            for well_plan in plan.wells:
                well_id = str(well_plan.well)
                if not well_id or len(well_id) < 2:
                    raise ValueError(f"Invalid well id '{well_id}'")

                params_obj = getattr(well_plan, "params", None)
                if params_obj is None:
                    raise ValueError(f"Well '{well_id}' has no mode parameters.")

                try:
                    params_payload = params_obj.to_payload()
                except NotImplementedError as exc:
                    raise ValueError(
                        f"Well '{well_id}' parameters do not support payload serialization."
                    ) from exc
                except AttributeError as exc:
                    raise ValueError(
                        f"Well '{well_id}' parameters are missing a to_payload() method."
                    ) from exc

                mode_label = str(well_plan.mode)
                box = well_id[0].upper()

                jobs.append(
                    {
                        "box": box,
                        "well_id": well_id,
                        "wells": [well_id],
                        "mode": mode_label,
                        "params": params_payload,
                        "tia_gain": plan.tia_gain,
                        "sampling_interval": plan.sampling_interval,
                        "make_plot": plan.make_plot,
                        "experiment_name": storage_payload["experiment_name"],
                        "subdir": storage_payload["subdir"],
                        "client_datetime": storage_payload["client_datetime"],
                    }
                )
                started_wells.append(str(well_plan.well))

            if not jobs:
                raise UseCaseError(
                    "START_FAILED", "No jobs could be constructed from the plan."
                )

            adapter_plan = {
                "jobs": jobs,
                "group_id": group_id,
                "storage": storage_payload,
            }
            run_group_id, per_box_runs = self.job_port.start_batch(adapter_plan)

            return StartBatchResult(
                run_group_id=run_group_id,
                per_box_runs=per_box_runs,
                started_wells=started_wells,
            )
        except UseCaseError:
            raise
        except Exception as e:
            raise UseCaseError("START_FAILED", str(e))
