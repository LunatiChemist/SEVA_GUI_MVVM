from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, List, Any, Iterable
from uuid import uuid4
import json

from seva.domain.ports import JobPort, UseCaseError, RunGroupId, BoxId
from seva.usecases.group_registry import set_planned_duration

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
    """Keep a mode-focused params dict; strip run_* flags."""
    return {
        k: v
        for k, v in snap.items()
        if not k.startswith("run_") and not k.startswith("eval_cdl")
    }


def _auto_run_name(box: str, mode: str, well_ids: List[str], group_id: str) -> str:
    """Generate a stable run_name per job."""
    nums = sorted(int(w[1:]) for w in well_ids if w and w[0] == box)
    short = group_id[:8]
    if not nums:
        return f"{box}-{mode}-{short}"
    if len(nums) == 1:
        return f"{box}-{mode}-well{nums[0]:02d}-{short}"
    return f"{box}-{mode}-well{nums[0]:02d}to{nums[-1]:02d}-{short}"


# Mode-specific planned duration estimator (same rules as discussed)
def _estimate_planned_duration(mode: str, params: Dict[str, Any]) -> int | None:
    def f(x, d=None):
        try:
            return float(x)
        except Exception:
            return d

    def i(x, d=None):
        try:
            return int(float(x))
        except Exception:
            return d

    setup = 5
    m = (mode or "").upper()

    if m == "DC":
        d1 = f(params.get("ea.duration_s"), None) or f(params.get("duration_s"), None)
        ctrl = str(params.get("control_mode") or "").lower()
        is_i = ("current" in ctrl) if ctrl else True
        i_ma = (
            f(params.get("ea.target_ma"), None)
            or f(params.get("target_ma"), None)
            or f(params.get("target"), None)
        )
        i_a = (i_ma / 1000.0) if (i_ma is not None) else None
        q_c = f(params.get("ea.charge_cutoff_c"), None) or f(
            params.get("charge_cutoff_c"), None
        )
        d2 = (q_c / i_a) if (is_i and i_a and i_a > 0 and q_c and q_c > 0) else None
        cand = [x for x in (d1, d2) if x and x > 0]
        return int(max(1, min(cand) + setup)) if cand else None

    if m == "AC":
        d = f(params.get("ea.duration_s"), None) or f(params.get("duration_s"), None)
        return int(d + setup) if d and d > 0 else None

    if m == "CV":
        v1 = f(params.get("cv.vertex1_v"), None)
        v2 = f(params.get("cv.vertex2_v"), None)
        scan = f(params.get("cv.scan_rate_v_s"), None) or f(
            params.get("scan_rate_v_s"), None
        )
        cycles = i(params.get("cv.cycles"), None) or i(params.get("cycles"), None)
        if (
            v1 is not None
            and v2 is not None
            and scan
            and scan > 0
            and cycles
            and cycles > 0
        ):
            span = abs(v2 - v1)
            t_cycle = 2.0 * span / scan
            return int(max(1, cycles * t_cycle + setup))
        return None

    if m == "LSV":
        sv = f(params.get("lsv.start_v"), None) or f(params.get("start_v"), None)
        ev = f(params.get("lsv.end_v"), None) or f(params.get("end_v"), None)
        scan = f(params.get("lsv.scan_rate_v_s"), None) or f(
            params.get("scan_rate_v_s"), None
        )
        if sv is not None and ev is not None and scan and scan > 0:
            return int(max(1, abs(ev - sv) / scan + setup))
        return None

    if m == "EIS":
        fs = f(params.get("eis.freq_start_hz"), None) or f(
            params.get("freq_start_hz"), None
        )
        fe = f(params.get("eis.freq_end_hz"), None) or f(
            params.get("freq_end_hz"), None
        )
        pts = i(params.get("eis.points"), None) or i(params.get("points"), None)
        sp = (
            (params.get("eis.spacing") or params.get("spacing") or "log")
            .strip()
            .lower()
        )
        cpf = i(params.get("eis.cycles_per_freq"), 3)
        if fs and fe and fs > 0 and fe > 0 and pts and pts > 1 and cpf > 0:
            freqs = []
            if sp == "lin":
                step = (fe - fs) / (pts - 1)
                freqs = [fs + k * step for k in range(pts)]
            else:
                r = (fe / fs) ** (1.0 / (pts - 1))
                freqs = [fs * (r**k) for k in range(pts)]
            total = sum((cpf / f) for f in freqs if f > 0)
            return int(max(1, total + setup))
        return None

    if m == "CDL":
        va = f(params.get("cdl.vertex_a_v"), None)
        vb = f(params.get("cdl.vertex_b_v"), None)
        scan = f(params.get("cv.scan_rate_v_s"), None) or f(
            params.get("scan_rate_v_s"), None
        )
        cycles = i(params.get("cdl.cycles"), 1)
        if (
            va is not None
            and vb is not None
            and scan
            and scan > 0
            and cycles
            and cycles > 0
        ):
            span = abs(va - vb)
            t_cycle = 2.0 * span / scan
            return int(max(1, cycles * t_cycle + setup))
        return None

    return None


@dataclass
class StartExperimentBatch:
    job_port: JobPort

    def __call__(self, plan: Dict) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        """
        Build jobs per Box and per identical signature, then post them via JobPort.
        Plan (input) must contain:
          - selection: List[WellId] (configured wells)
          - well_params_map: Dict[WellId, Dict[str,str]] (per-well snapshots incl. run_* flags)
          - optional: folder_name, tia_gain, sampling_interval, make_plot, group_id
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
            folder_name = plan.get("folder_name") or group_id
            tia_gain = plan.get("tia_gain", None)
            sampling_interval = plan.get("sampling_interval", None)
            make_plot = bool(plan.get("make_plot", True))

            # Box -> signature -> [wells]
            per_box: Dict[
                BoxId,
                Dict[Tuple[str, str, int | None, float | None, bool, str], List[str]],
            ] = {}

            for wid in selection:
                if not wid or len(wid) < 2:
                    raise ValueError(f"Invalid well id '{wid}'")
                box = wid[0].upper()  # route by prefix only
                snap = wmap.get(wid)
                if not snap:
                    raise ValueError(f"No saved parameters for well '{wid}'")

                mode = _derive_mode(snap)
                params = _normalize_params(mode, snap)
                params_key = json.dumps(params, sort_keys=True)

                signature = (
                    mode,
                    params_key,
                    tia_gain,
                    sampling_interval,
                    make_plot,
                    folder_name,
                )
                per_box.setdefault(box, {}).setdefault(signature, []).append(wid)

            # Build concrete job list
            jobs: List[Dict[str, Any]] = []
            for box, sigs in per_box.items():
                for signature, wells in sigs.items():
                    mode, params_key, tg, si, mp, folder = signature
                    params = json.loads(params_key)
                    jobs.append(
                        {
                            "box": box,
                            "wells": sorted(set(wells)),
                            "mode": mode,
                            "params": params,
                            "tia_gain": tg,
                            "sampling_interval": si,
                            "folder_name": folder,
                            "make_plot": mp,
                            "run_name": _auto_run_name(box, mode, wells, group_id),
                        }
                    )

            # Call adapter with pre-grouped jobs
            adapter_plan = {"jobs": jobs, "group_id": group_id}
            run_group_id, per_box_runs = self.job_port.start_batch(adapter_plan)

            # Store planned duration per run (mode-specific) for client-side progress
            for job in jobs:
                box = job["box"]
                mode = job["mode"]
                params = job["params"]
                run_list = per_box_runs.get(box, [])
                # Heuristic: map in the order we posted jobs per box
                # (jobs appended per signature; adapter returns per box in the same order)
                if not run_list:
                    continue
                run_id = run_list.pop(0)
                planned = _estimate_planned_duration(mode, params)
                set_planned_duration(run_group_id, run_id, planned, mode=mode)

            return run_group_id, per_box_runs
        except Exception as e:
            raise UseCaseError("START_FAILED", str(e))
