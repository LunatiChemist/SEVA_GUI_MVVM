# seva/adapters/job_rest.py
from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple, Optional, Any, List
from uuid import uuid4

import requests

# Domain Port
from seva.domain.ports import JobPort, RunGroupId, BoxId


@dataclass
class _HttpConfig:
    request_timeout_s: int = 10
    download_timeout_s: int = 60
    retries: int = 2


class _RetryingSession:
    """Tiny requests wrapper with X-API-Key and simple retry.
    Future: move to infra with exponential backoff + jitter.
    """

    def __init__(self, api_key: Optional[str], cfg: _HttpConfig) -> None:
        self.session = requests.Session()
        self.api_key = api_key
        self.cfg = cfg

    def _headers(
        self, accept: str = "application/json", json_body: bool = False
    ) -> Dict[str, str]:
        h = {"Accept": accept}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        accept: str = "application/json",
        timeout: Optional[int] = None,
        stream: bool = False,
    ):
        last_err: Optional[Exception] = None
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.get(
                    url,
                    params=params,
                    headers=self._headers(accept=accept),
                    timeout=timeout or self.cfg.request_timeout_s,
                    stream=stream,
                )
            except Exception as e:
                last_err = e
        raise last_err  # type: ignore[misc]

    def post(
        self,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ):
        last_err: Optional[Exception] = None
        data = None if json_body is None else json.dumps(json_body)
        for _ in range(self.cfg.retries + 1):
            try:
                return self.session.post(
                    url,
                    data=data,
                    headers=self._headers(json_body=json_body is not None),
                    timeout=timeout or self.cfg.request_timeout_s,
                )
            except Exception as e:
                last_err = e
        raise last_err  # type: ignore[misc]


class JobRestAdapter(JobPort):
    """REST adapter for your FastAPI boxes.

    Endpoints:
      - POST {base}/jobs               body: {"devices":[1,2], "mode":"CV|CA|LSV|...", "params":{...}}
              -> {"run_id": "..."}
      - GET  {base}/jobs/{run_id}      -> {"run_id": "...", "started_at": "...",
                                            "channels":[{"slot":1,"state":"Running"}, ...]}
      - GET  {base}/runs/{run_id}/zip  -> application/zip

    Notes:
      - Cancel: not implemented server-side → we only print a notice.
      - Box list is dynamic from base_urls keys (alphabetic order).
      - Well/slot mapping uses a prebuilt registry (no ad-hoc arithmetic in call sites).
    """

    def __init__(
        self,
        base_urls: Dict[BoxId, str],
        api_keys: Optional[Dict[BoxId, str]] = None,
        request_timeout_s: int = 10,
        download_timeout_s: int = 60,
        retries: int = 2,
    ) -> None:
        self.base_urls = dict(base_urls)
        self.api_keys = dict(api_keys or {})
        self.cfg = _HttpConfig(
            request_timeout_s=request_timeout_s,
            download_timeout_s=download_timeout_s,
            retries=retries,
        )
        # Dynamic, alphabetic box order
        self.box_order: List[BoxId] = sorted(self.base_urls.keys())

        # Sessions per box
        self.sessions: Dict[BoxId, _RetryingSession] = {
            b: _RetryingSession(self.api_keys.get(b), self.cfg)
            for b in self.base_urls.keys()
        }

        # Client-side group mapping: group_id -> {box -> run_id}
        self._groups: Dict[RunGroupId, Dict[BoxId, str]] = {}

        # Precompute registry well_id <-> (box, slot)
        self.well_to_slot: Dict[str, Tuple[BoxId, int]] = {}
        self.slot_to_well: Dict[Tuple[BoxId, int], str] = {}
        self._build_registry()

    # ---------- Registry ----------

    def _build_registry(self) -> None:
        """Build well_id ↔ (box,slot) mapping harmonized with WellGrid IDs.
        Pattern: for each box in alphabetic order, slots 1..10 map to
        A1..A10, B11..B20, C21..C30, ...
        """
        for idx, box in enumerate(self.box_order):
            base = idx * 10
            for slot in range(1, 11):
                global_num = base + slot
                well_id = f"{box}{global_num}"
                self.well_to_slot[well_id] = (box, slot)
                self.slot_to_well[(box, slot)] = well_id

    # ---------- JobPort implementation ----------

    def start_batch(self, plan: Dict) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        """
        Fan-out by Box, then group slots inside a Box by identical signature.
        One JobRequest per (Box, Signature). Multiple jobs per Box are supported.

        Expected plan keys:
        - selection: List[WellId]
        - well_params_map: Dict[WellId, Dict[str,str]]
        - (optional) tia_gain, sampling_interval, make_plot, folder_name, group_id
        """
        # 1) Validate plan
        selection: Iterable[str] = plan.get("selection") or []
        selection = list(selection)
        if not selection:
            raise ValueError("start_batch: empty selection")

        well_params_map: Dict[str, Dict[str, str]] = plan.get("well_params_map") or {}
        if not well_params_map:
            raise ValueError("start_batch: missing well_params_map")

        group_id: RunGroupId = plan.get("group_id") or str(uuid4())
        folder_name: Optional[str] = plan.get("folder_name") or group_id
        tia_gain = plan.get("tia_gain", None)
        sampling_interval = plan.get("sampling_interval", None)
        make_plot = bool(plan.get("make_plot", True))

        # 2) Build Box → [(slot, snapshot)]
        per_box: Dict[BoxId, List[Tuple[int, Dict[str, str]]]] = {}
        for wid in selection:
            tpl = self.well_to_slot.get(wid)
            if not tpl:
                raise ValueError(f"Unknown well id '{wid}' for configured boxes {self.box_order}")
            box, slot = tpl
            snap = well_params_map.get(wid)
            if not snap:
                raise ValueError(f"No saved parameters for well '{wid}'")
            per_box.setdefault(box, []).append((slot, snap))

        # Prepare group mapping: box -> [run_id, ...]
        run_ids: Dict[BoxId, List[str]] = {}
        self._groups[group_id] = {}

        # 3) Inside each Box: group slots by signature and post one JobRequest per signature
        #    Signature = (mode, normalized_params_json, tia_gain, sampling_interval, make_plot, folder_name)
        for box, items in per_box.items():
            sig_to_slots: Dict[Tuple[str, str, Optional[int], Optional[float], bool, str], List[int]] = {}
            sig_to_params: Dict[Tuple[str, str, Optional[int], Optional[float], bool, str], Dict[str, str]] = {}

            for slot, snap in items:
                mode = self._derive_mode(snap)
                params = self._normalize_params(mode, snap)
                params_key = json.dumps(params, sort_keys=True)
                signature = (mode, params_key, tia_gain, sampling_interval, make_plot, folder_name)
                sig_to_slots.setdefault(signature, []).append(slot)
                sig_to_params[signature] = params

            for signature, slots in sig_to_slots.items():
                mode, params_key, tia_g, samp_i, mk_plot, folder = signature
                params = sig_to_params[signature]
                slots = sorted(slots)

                payload = {
                    "devices": [self._slot_label(s) for s in slots],
                    "mode": mode,
                    "params": params,
                    "tia_gain": tia_g,
                    "sampling_interval": samp_i,
                    "run_name": self._auto_run_name(box, mode, slots, group_id),
                    "folder_name": folder,
                    "make_plot": mk_plot,
                }

                url = self._make_url(box, "/jobs")
                resp = self.sessions[box].post(url, json_body=payload, timeout=self.cfg.request_timeout_s)
                self._ensure_ok(resp, f"start[{box}]")
                data = self._json(resp)
                run_id = str(data.get("run_id") or payload["run_name"])

                self._groups[group_id].setdefault(box, []).append(run_id)
                run_ids.setdefault(box, []).append(run_id)

        return group_id, run_ids

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        print("Cancel not implemented on API side.")

    def poll_group(self, run_group_id: RunGroupId) -> Dict:
        """
        Poll status for ALL run_ids per box and return a raw snapshot.
        We do NOT compute % here (UseCase handles that). No finished_at expected.

        Returns:
        {
            "boxes": {
            "A": {
                "runs": [ {"run_id": "...", "status": "running|done|failed", "started_at": "iso|None"} , ... ],
                "phase": "Queued|Running|Done|Failed|Mixed",
                "subrun": "runA1, runA2"  # CSV of run_ids
            },
            ...
            },
            "wells": [ (well_id, slot_status, 0, message, run_id), ... ],
            "activity": { well_id: slot_status, ... }
        }
        """
        box_runs: Dict[BoxId, List[str]] = self._groups.get(run_group_id, {}) or {}
        snapshot = {"boxes": {}, "wells": [], "activity": {}}

        for box, run_list in box_runs.items():
            run_entries = []
            phases = set()

            for run_id in run_list:
                url = self._make_url(box, f"/jobs/{run_id}")
                resp = self.sessions[box].get(url, timeout=self.cfg.request_timeout_s)
                if resp.status_code == 404:
                    # Unknown/queued from server view; keep placeholder
                    run_entries.append(
                        {"run_id": run_id, "status": "queued", "started_at": None}
                    )
                    phases.add("Queued")
                    continue

                self._ensure_ok(resp, f"status[{box}]")
                data = self._json(resp)

                job_status = str(data.get("status") or "queued").lower()
                started_at = data.get("started_at")  # ISO or None
                run_entries.append(
                    {
                        "run_id": str(data.get("run_id") or run_id),
                        "status": job_status,
                        "started_at": started_at,
                    }
                )
                phases.add(job_status.capitalize())

                # Slots → per-well rows & activity
                for slot_info in data.get("slots") or []:
                    # API model: {slot: "slot01", status: "running|done|failed", message: str, files: [...]}
                    slot_label = slot_info.get("slot")  # "slotNN"
                    try:
                        slot_num = int(str(slot_label).replace("slot", ""))
                    except Exception:
                        continue
                    wid = self.slot_to_well.get((box, slot_num))
                    if not wid:
                        continue
                    s_status = str(slot_info.get("status") or "queued").capitalize()
                    s_msg = slot_info.get("message") or ""
                    snapshot["wells"].append(
                        (wid, s_status, 0, s_msg, str(data.get("run_id") or run_id))
                    )
                    snapshot["activity"][wid] = s_status

            # Box-level aggregation (no percentages here)
            if not run_entries:
                box_phase = "Queued"
            else:
                up = {e["status"].capitalize() for e in run_entries}
                box_phase = "Mixed" if len(up) > 1 else next(iter(up))

            snapshot["boxes"][box] = {
                "runs": run_entries,
                "phase": box_phase,
                "subrun": (
                    ", ".join([e["run_id"] for e in run_entries]) if run_entries else None
                ),
            }

        return snapshot

    def download_group_zip(self, run_group_id: RunGroupId, target_dir: str) -> str:
        """
        Download all run zips for all boxes in the group into:
        <target_dir>/<group_id>/<box>/<run_id>.zip
        Returns the output folder path.
        """
        box_runs: Dict[BoxId, List[str]] = self._groups.get(run_group_id, {}) or {}
        out_dir = os.path.join(target_dir, str(run_group_id))
        os.makedirs(out_dir, exist_ok=True)

        for box, runs in box_runs.items():
            box_dir = os.path.join(out_dir, box)
            os.makedirs(box_dir, exist_ok=True)
            for run_id in runs:
                url = self._make_url(box, f"/runs/{run_id}/zip")
                resp = self.sessions[box].get(
                    url,
                    timeout=self.cfg.download_timeout_s,
                    stream=True,
                    accept="application/zip",
                )
                if resp.status_code == 404:
                    continue
                self._ensure_ok(resp, f"download[{box}:{run_id}]")

                path = os.path.join(box_dir, f"{run_id}.zip")
                with open(path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

        return out_dir

    # ---------- helpers ----------

    def _make_url(self, box: BoxId, path: str) -> str:
        base = self.base_urls.get(box)
        if not base:
            raise ValueError(f"No base URL configured for box '{box}'")
        if base.endswith("/"):
            base = base[:-1]
        return f"{base}{path}"

    def _slot_label(self, slot: int) -> str:
        return f"slot{slot:02d}"

    def _derive_mode(self, snap: Dict[str, str]) -> str:
        # Determine mode from run_* flags (exactly one must be true)
        flags = {
            "CV": snap.get("run_cv"),
            "DC": snap.get("run_dc"),
            "AC": snap.get("run_ac"),
            "LSV": snap.get("run_lsv"),
            "EIS": snap.get("run_eis"),
        }
        picked = [m for m, v in flags.items() if str(v).strip().lower() in ("1","true","yes","on")]
        if len(picked) != 1:
            raise ValueError(f"Exactly one run_* flag must be set (got {picked or 'none'}).")
        return picked[0]

    def _normalize_params(self, mode: str, snap: Dict[str, str]) -> Dict[str, str]:
        """
        Keep this pragmatic for now: pass through the snapshot as params,
        but strip the run_* flags themselves.
        Future: mode-specific schema filtering (Controller's /modes/{mode}/params).
        """
        params = {k: v for k, v in snap.items() if not k.startswith("run_")}
        return params

    def _auto_run_name(self, box: str, mode: str, slots: List[int], group_id: str) -> str:
        short = group_id[:8]
        if not slots:
            return f"{box}-{mode}-{short}"
        smin, smax = min(slots), max(slots)
        if smin == smax:
            return f"{box}-{mode}-slot{ smin:02d }-{short}"
        return f"{box}-{mode}-slot{ smin:02d }to{ smax:02d }-{short}"

    # ---- Duration estimation helpers (mode-specific) ----
    def _to_float(self, v, default=None):
        try:
            return float(v)
        except Exception:
            return default


    def _to_int(self, v, default=None):
        try:
            return int(float(v))
        except Exception:
            return default


    def _is_true(self, v) -> bool:
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "on")


    def _estimate_planned_duration(
        self, mode: str, params: Dict[str, Any]
    ) -> Optional[int]:
        """
        Estimate planned duration (seconds) per run_id based on mode-specific parameters.
        Returns None if not enough information is available.

        Rules of thumb (kept simple and robust):
        - Always clamp to positive numbers and add a small setup buffer.
        - If multiple cues exist (e.g., DC duration & charge cutoff), take the MIN.
        - Units assumptions:
            * currents may be entered in mA (we try 'ea.target_ma' first, fallback to 'target' heuristic)
            * times are seconds
        """
        setup_buffer_s = 5

        mode = (mode or "").strip().upper()

        # ---------- DC (constant electrolysis) ----------
        if mode == "DC":
            # primary duration
            d1 = self._to_float(params.get("ea.duration_s"), None) or self._to_float(
                params.get("duration_s"), None
            )

            # secondary from charge cutoff if current-controlled
            # detect current control
            ctrl = str(params.get("control_mode") or "").lower()
            is_current_control = (
                ("current" in ctrl) if ctrl else True
            )  # default to current if unknown

            # try to extract target current (in A)
            i_ma = self._to_float(params.get("ea.target_ma"), None)
            if i_ma is None:
                i_ma = self._to_float(params.get("target_ma"), None)
            if i_ma is None:
                # generic 'target' often comes from combobox; take if numeric
                i_ma = self._to_float(params.get("target"), None)

            i_a = (i_ma / 1000.0) if (i_ma is not None) else None
            q_c = self._to_float(params.get("ea.charge_cutoff_c"), None) or self._to_float(
                params.get("charge_cutoff_c"), None
            )

            d2 = None
            if (
                is_current_control
                and (i_a is not None)
                and (i_a > 0)
                and (q_c is not None)
                and (q_c > 0)
            ):
                d2 = q_c / i_a

            # take min positive candidate
            candidates = [x for x in (d1, d2) if (x is not None and x > 0)]
            if candidates:
                return int(max(1, min(candidates) + setup_buffer_s))
            return None

        # ---------- AC (alternating electrolysis) ----------
        if mode == "AC":
            d = self._to_float(params.get("ea.duration_s"), None) or self._to_float(
                params.get("duration_s"), None
            )
            if d and d > 0:
                return int(d + setup_buffer_s)
            # If later we support "cycles" at frequency: duration ≈ cycles / f
            return None

        # ---------- CV (cyclic voltammetry) ----------
        if mode == "CV":
            v1 = self._to_float(params.get("cv.vertex1_v"), None)
            v2 = self._to_float(params.get("cv.vertex2_v"), None)
            scan = self._to_float(params.get("cv.scan_rate_v_s"), None) or self._to_float(
                params.get("scan_rate_v_s"), None
            )
            cycles = self._to_int(params.get("cv.cycles"), None) or self._to_int(
                params.get("cycles"), None
            )
            if (
                v1 is not None
                and v2 is not None
                and scan
                and scan > 0
                and cycles
                and cycles > 0
            ):
                span = abs(v2 - v1)
                t_cycle = 2.0 * span / scan  # forward + backward
                # optional final leg (often negligible – ignore for now)
                dur = cycles * t_cycle + setup_buffer_s
                return int(max(1, dur))
            return None

        # ---------- LSV (linear sweep) ----------
        if mode == "LSV":
            start_v = self._to_float(params.get("lsv.start_v"), None) or self._to_float(
                params.get("start_v"), None
            )
            end_v = self._to_float(params.get("lsv.end_v"), None) or self._to_float(
                params.get("end_v"), None
            )
            scan = self._to_float(params.get("lsv.scan_rate_v_s"), None) or self._to_float(
                params.get("scan_rate_v_s"), None
            )
            if start_v is not None and end_v is not None and scan and scan > 0:
                dur = abs(end_v - start_v) / scan + setup_buffer_s
                return int(max(1, dur))
            return None

        # ---------- EIS (impedance) ----------
        if mode == "EIS":
            f_start = self._to_float(
                params.get("eis.freq_start_hz"), None
            ) or self._to_float(params.get("freq_start_hz"), None)
            f_end = self._to_float(params.get("eis.freq_end_hz"), None) or self._to_float(
                params.get("freq_end_hz"), None
            )
            points = self._to_int(params.get("eis.points"), None) or self._to_int(
                params.get("points"), None
            )
            spacing = (
                (params.get("eis.spacing") or params.get("spacing") or "log")
                .strip()
                .lower()
            )
            cycles_per_freq = (
                self._to_int(params.get("eis.cycles_per_freq"), None) or 3
            )  # heuristic default
            if (
                f_start
                and f_end
                and f_start > 0
                and f_end > 0
                and points
                and points > 1
                and cycles_per_freq > 0
            ):
                freqs = []
                if spacing == "lin":
                    step = (f_end - f_start) / (points - 1)
                    freqs = [f_start + i * step for i in range(points)]
                else:
                    r = (f_end / f_start) ** (1.0 / (points - 1))
                    freqs = [f_start * (r**i) for i in range(points)]
                # time per frequency ~ cycles / f
                total = 0.0
                for f in freqs:
                    if f > 0:
                        total += cycles_per_freq / f
                return int(max(1, total + setup_buffer_s))
            return None

        # ---------- CDL (capacitance) ----------
        if mode == "CDL":
            va = self._to_float(params.get("cdl.vertex_a_v"), None)
            vb = self._to_float(params.get("cdl.vertex_b_v"), None)
            scan = self._to_float(params.get("cv.scan_rate_v_s"), None) or self._to_float(
                params.get("scan_rate_v_s"), None
            )
            cycles = self._to_int(params.get("cdl.cycles"), 1)  # assume 1 if missing
            if va is not None and vb is not None and scan and scan > 0 and cycles > 0:
                span = abs(va - vb)
                t_cycle = 2.0 * span / scan
                dur = cycles * t_cycle + setup_buffer_s
                return int(max(1, dur))
            return None

        # Unknown mode → no estimate
        return None

    @staticmethod
    def _ensure_ok(resp: requests.Response, ctx: str) -> None:
        if 200 <= resp.status_code < 300:
            return
        body = ""
        try:
            body = resp.text[:300]
        except Exception:
            pass
        raise RuntimeError(f"{ctx}: HTTP {resp.status_code} {body}")

    @staticmethod
    def _json(resp: requests.Response) -> Dict[str, Any]:
        try:
            return resp.json()
        except Exception:
            txt = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {txt}")
