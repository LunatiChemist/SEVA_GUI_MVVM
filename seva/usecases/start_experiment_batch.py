from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Any, Iterable, Callable, Optional
from uuid import uuid4

from seva.domain.ports import (
    BoxId,
    DevicePort,
    JobPort,
    RunGroupId,
    UseCaseError,
    WellId,
)

# ---- Mode parameter mapping ----


def _map_params_cv(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Project CV snapshot fields to the REST API payload."""

    def _coerce_float(value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return value
            value = stripped
        try:
            return float(value)
        except Exception:
            # TODO(validation): enforce numeric input once validation layer exists.
            return value

    def _coerce_int(value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return value
            value = stripped
        try:
            return int(float(value))
        except Exception:
            # TODO(validation): enforce numeric input once validation layer exists.
            return value

    start_raw = snapshot.get("cv.start_v")
    if start_raw is None or (isinstance(start_raw, str) and not start_raw.strip()):
        start_value: Any = 0.0
    else:
        start_value = _coerce_float(start_raw)

    return {
        "start": start_value,
        "vertex1": _coerce_float(snapshot.get("cv.vertex1_v")),
        "vertex2": _coerce_float(snapshot.get("cv.vertex2_v")),
        "end": _coerce_float(snapshot.get("cv.final_v")),
        "scan_rate": _coerce_float(snapshot.get("cv.scan_rate_v_s")),
        "cycles": _coerce_int(snapshot.get("cv.cycles")),
    }


_MAPPER_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "CV": _map_params_cv,
    # TODO(mode:EIS): add mapper when EIS mapping is defined.
    # TODO(mode:CDL): add mapper when CDL mapping is defined.
    # TODO(mode:DC): add mapper when DC mapping is defined.
    # TODO(mode:AC): add mapper when AC mapping is defined.
}


def map_params(mode: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Apply mode-specific parameter mapping, keeping legacy fields as fallback."""
    mapper = _MAPPER_REGISTRY.get((mode or "").upper())
    if not mapper:
        # TODO: replace with strict mapping once mode is implemented.
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
    return mapper(snapshot)

# ---- Local helpers (UseCase-level) ----

def _derive_mode(snap: Dict[str, str]) -> str:
    """Pick exactly one run_* flag as mode. Raises if none/multiple."""
    flags = {
        "CV": snap.get("run_cv"),
        "DC": snap.get("run_dc"),
        "AC": snap.get("run_ac"),
        "LSV": snap.get("run_lsv"),
        "EIS": snap.get("run_eis"),
        "CDL": snap.get("run_cdl") or snap.get("eval_cdl"),
    }
    picked = [
        m
        for m, v in flags.items()
        if str(v).strip().lower() in ("1", "true", "yes", "on")
    ]
    if len(picked) != 1:
        raise ValueError(
            f"Exactly one run_* flag must be set (got {picked or 'none'})."
        )
    return picked[0]


def _normalize_params(mode: str, snap: Dict[str, str]) -> Dict[str, Any]:
    """Keep a mode-focused params dict via map_params for backward compatibility."""
    return map_params(mode, snap)

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
    started_wells: List[WellId]
    validations: List[WellValidationResult]


@dataclass
class StartExperimentBatch:
    job_port: JobPort
    device_port: DevicePort

    def __call__(self, plan: Dict) -> StartBatchResult:
        """
        Build one job per configured well and post them via JobPort.
        Coordinator must run ValidateStartPlan beforehand. This use case
        does not perform validation and does not partial-start. It builds
        one job per well and submits the full batch.
        Plan (input) must contain:
          - selection: List[WellId] (configured wells)
          - well_params_map: Dict[WellId, Dict[str,str]] (per-well snapshots incl. run_* flags)
          - optional: tia_gain, sampling_interval, make_plot, group_id
        """
        try:
            selection: Iterable[str] = plan.get("selection") or []
            selection = list(selection)
            if not selection:
                raise ValueError("Start plan has no wells (selection is empty).")

            wmap: Dict[str, Dict[str, str]] = plan.get("well_params_map") or {}
            if not wmap:
                raise ValueError(
                    "Start plan has no per-well parameters (well_params_map missing)."
                )

            group_id: RunGroupId = plan.get("group_id") or str(uuid4())
            tia_gain = plan.get("tia_gain", None)
            sampling_interval = plan.get("sampling_interval", None)
            make_plot = bool(plan.get("make_plot", True))
            storage_raw = plan.get("storage") or {}

            def _clean_text(value: Any) -> str:
                return str(value).strip() if isinstance(value, str) else ""

            experiment_name = _clean_text(storage_raw.get("experiment_name"))
            if not experiment_name:
                raise UseCaseError(
                    "METADATA_MISSING", "Experiment name must be configured."
                )
            subdir_value = _clean_text(storage_raw.get("subdir"))
            client_datetime = _clean_text(storage_raw.get("client_datetime"))
            if not client_datetime:
                client_datetime = (
                    datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )

            storage_payload = {
                "experiment_name": experiment_name,
                "subdir": subdir_value or None,
                "client_datetime": client_datetime,
            }

            jobs: List[Dict[str, Any]] = []
            for wid in selection:
                if not wid or len(wid) < 2:
                    raise ValueError(f"Invalid well id '{wid}'")
                box = wid[0].upper()  # route by prefix only
                snap = wmap.get(wid)
                if not snap:
                    raise ValueError(f"No saved parameters for well '{wid}'")

                mode = _derive_mode(snap)
                params = _normalize_params(mode, snap)

                jobs.append(
                    {
                        "box": box,
                        "well_id": wid,
                        "wells": [wid],
                        "mode": mode,
                        "params": params,
                        "tia_gain": tia_gain,
                        "sampling_interval": sampling_interval,
                        "make_plot": make_plot,
                        "experiment_name": storage_payload["experiment_name"],
                        "subdir": storage_payload["subdir"],
                        "client_datetime": storage_payload["client_datetime"],
                    }
                )

            if not jobs:
                raise UseCaseError("START_FAILED", "No jobs could be constructed from the plan.")

            # Call adapter with one job per well
            adapter_plan = {
                "jobs": jobs,
                "group_id": group_id,
                "storage": storage_payload,
            }
            run_group_id, per_box_runs = self.job_port.start_batch(adapter_plan)

            return StartBatchResult(
                run_group_id=run_group_id,
                per_box_runs=per_box_runs,
                started_wells=list(selection),
                validations=[],
            )
        except UseCaseError:
            raise
        except Exception as e:
            raise UseCaseError("START_FAILED", str(e))
