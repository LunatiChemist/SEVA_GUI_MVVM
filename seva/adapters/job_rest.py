# seva/adapters/job_rest.py
from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple, Optional, Any, List, Set
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
      - Cancel: not implemented server-side -> we only print a notice.
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

        # Cached run snapshots + terminal tracking
        self._run_cache: Dict[str, Dict[str, Any]] = {}
        self._terminal_runs: Set[str] = set()

    # ---------- Registry ----------

    def _build_registry(self) -> None:
        """Build well_id <-> (box,slot) mapping harmonized with WellGrid IDs.
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

    def health(self, box_id: BoxId) -> Dict:
        session = self.sessions.get(box_id)
        if session is None:
            raise ValueError(f"No session configured for box '{box_id}'")
        url = self._make_url(box_id, "/health")
        resp = session.get(url, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"health[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError(f"health[{box_id}]: expected dict response")
        return data

    def list_devices(self, box_id: BoxId) -> List[Dict]:
        session = self.sessions.get(box_id)
        if session is None:
            raise ValueError(f"No session configured for box '{box_id}'")
        url = self._make_url(box_id, "/devices")
        resp = session.get(url, timeout=self.cfg.request_timeout_s)
        self._ensure_ok(resp, f"devices[{box_id}]")
        data = self._json_any(resp)
        if not isinstance(data, list):
            raise RuntimeError(f"devices[{box_id}]: expected list response")
        cleaned: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                cleaned.append(item)
        return cleaned

    def start_batch(self, plan: Dict) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        """
        Post pre-grouped jobs (built by the UseCase) to each box.
        Expected plan keys:
        - jobs: List[Dict] where each job contains:
            { "box": "A", "wells": ["A1","A5",...], "mode": "CV|DC|AC|LSV|EIS|CDL",
                "params": {...}, "tia_gain": int|None, "sampling_interval": float|None,
                "folder_name": str|None, "make_plot": bool, "run_name": str }
        - (optional) group_id
        Returns:
        (group_id, { box: [run_id, ...] })
        """
        jobs: List[Dict[str, Any]] = plan.get("jobs") or []
        if not jobs:
            raise ValueError("start_batch: missing 'jobs' in plan")

        group_id: RunGroupId = plan.get("group_id") or str(uuid4())

        # Prepare mapping: group_id -> box -> [run_id,...]
        run_ids: Dict[BoxId, List[str]] = {}
        self._groups[group_id] = {}

        for job in jobs:
            box: BoxId = job.get("box")
            wells: List[str] = list(job.get("wells") or [])
            if not box or not wells:
                raise ValueError("start_batch: job requires 'box' and non-empty 'wells'")

            # Map wells -> slot labels for this box
            slots: List[int] = []
            for wid in wells:
                tpl = self.well_to_slot.get(wid)
                if not tpl or tpl[0] != box:
                    raise ValueError(f"Unknown or mismatched well '{wid}' for box '{box}'")
                slots.append(tpl[1])
            devices = [self._slot_label(s) for s in sorted(set(slots))]

            payload = {
                "devices": devices,
                "mode": job.get("mode"),
                "params": job.get("params") or {},
                "tia_gain": job.get("tia_gain", None),
                "sampling_interval": job.get("sampling_interval", None),
                "run_name": job.get("run_name"),
                "folder_name": job.get("folder_name") or group_id,
                "make_plot": bool(job.get("make_plot", True)),
            }

            url = self._make_url(box, "/jobs")
            resp = self.sessions[box].post(
                url, json_body=payload, timeout=self.cfg.request_timeout_s
            )
            self._ensure_ok(resp, f"start[{box}]")
            data = self._json(resp)
            run_id = str(data.get("run_id") or payload["run_name"])

            self._groups[group_id].setdefault(box, []).append(run_id)
            run_ids.setdefault(box, []).append(run_id)

            normalized = self._normalize_job_status(
                box, data, fallback_run_id=run_id
            )
            self._store_run_snapshot(normalized)

        return group_id, run_ids

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        print("Cancel not implemented on API side.")

    def poll_group(self, run_group_id: RunGroupId) -> Dict:
        """Bulk poll run snapshots using POST /jobs/status and cached terminals."""
        box_runs: Dict[BoxId, List[str]] = self._groups.get(run_group_id, {}) or {}
        snapshot = {"boxes": {}, "wells": [], "activity": {}}

        has_runs = False
        all_terminal = True

        for box, run_list in box_runs.items():
            unique_runs: List[str] = list(dict.fromkeys(run_list))
            if not unique_runs:
                snapshot["boxes"][box] = {"runs": [], "phase": "Queued", "subrun": None}
                all_terminal = False
                continue

            pending_ids: List[str] = []
            for run_id in unique_runs:
                if run_id not in self._terminal_runs:
                    pending_ids.append(run_id)

            if pending_ids:
                url = self._make_url(box, "/jobs/status")
                resp = self.sessions[box].post(
                    url,
                    json_body={"run_ids": pending_ids},
                    timeout=self.cfg.request_timeout_s,
                )
                self._ensure_ok(resp, f"status[{box}]")
                payload = self._json_any(resp)
                if not isinstance(payload, list):
                    raise RuntimeError("Invalid JSON response: expected list of runs")
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    normalized = self._normalize_job_status(box, item)
                    self._store_run_snapshot(normalized)

            run_entries: List[Dict[str, Any]] = []
            statuses_capitalized: Set[str] = set()
            box_has_incomplete = False

            for run_id in unique_runs:
                data = self._run_cache.get(run_id)
                if not data:
                    data = {
                        "box": box,
                        "run_id": run_id,
                        "status": "queued",
                        "started_at": None,
                        "ended_at": None,
                        "progress_pct": 0,
                        "remaining_s": None,
                        "slots": [],
                    }
                    self._run_cache[run_id] = data
                    self._terminal_runs.discard(run_id)

                status = str(data.get("status") or "queued").lower()
                run_entry = {
                    "run_id": data.get("run_id", run_id),
                    "status": status,
                    "started_at": data.get("started_at"),
                    "ended_at": data.get("ended_at"),
                    "progress_pct": data.get("progress_pct", 0),
                    "remaining_s": data.get("remaining_s"),
                }
                run_entries.append(run_entry)
                statuses_capitalized.add(run_entry["status"].capitalize())

                if not self._is_terminal(status):
                    box_has_incomplete = True

                for slot_info in data.get("slots") or []:
                    slot_label = slot_info.get("slot")
                    try:
                        slot_num = int(str(slot_label).replace("slot", ""))
                    except Exception:
                        continue
                    wid = self.slot_to_well.get((box, slot_num))
                    if not wid:
                        continue
                    raw = str(slot_info.get("status") or "queued").lower()
                    s_status = (
                        "Error"
                        if raw == "failed"
                        else (
                            "Done"
                            if raw == "done"
                            else ("Running" if raw == "running" else "Queued")
                        )
                    )
                    s_msg = slot_info.get("message") or ""
                    snapshot["wells"].append(
                        (
                            wid,
                            s_status,
                            data.get("progress_pct", 0),
                            s_msg,
                            run_entry["run_id"],
                        )
                    )
                    snapshot["activity"][wid] = s_status

            if run_entries:
                has_runs = True
            else:
                all_terminal = False

            if not run_entries:
                box_phase = "Queued"
            elif len(statuses_capitalized) == 1:
                box_phase = next(iter(statuses_capitalized))
            else:
                box_phase = "Mixed"

            snapshot["boxes"][box] = {
                "runs": run_entries,
                "phase": box_phase,
                "subrun": ", ".join(entry["run_id"] for entry in run_entries)
                if run_entries
                else None,
            }

            if box_has_incomplete:
                all_terminal = False

        snapshot["all_done"] = bool(box_runs) and has_runs and all_terminal
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

    def _store_run_snapshot(self, snapshot: Dict[str, Any]) -> None:
        run_id = snapshot.get("run_id")
        if not run_id:
            return
        self._run_cache[run_id] = snapshot
        status = str(snapshot.get("status") or "").lower()
        if self._is_terminal(status):
            self._terminal_runs.add(run_id)
        else:
            self._terminal_runs.discard(run_id)

    @staticmethod
    def _is_terminal(status: str) -> bool:
        normalized = status.lower()
        return normalized in {"done", "failed", "canceled", "cancelled"}

    def _normalize_job_status(
        self, box: BoxId, payload: Dict[str, Any], *, fallback_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid job status payload: expected object")
        run_id_raw = payload.get("run_id") or fallback_run_id
        if not run_id_raw:
            raise RuntimeError("Job status payload missing run_id")
        run_id = str(run_id_raw)
        status = str(payload.get("status") or "queued").lower()
        progress_raw = payload.get("progress_pct")
        try:
            progress_pct = int(progress_raw)
        except Exception:
            progress_pct = 0
        remaining_raw = payload.get("remaining_s")
        if isinstance(remaining_raw, (int, float)):
            remaining_s: Optional[int] = int(remaining_raw)
        elif remaining_raw is not None:
            try:
                remaining_s = int(float(remaining_raw))
            except Exception:
                remaining_s = None
        else:
            remaining_s = None
        slots_raw = payload.get("slots") or []
        slots: List[Dict[str, Any]] = []
        for slot in slots_raw:
            if not isinstance(slot, dict):
                continue
            slots.append(
                {
                    "slot": slot.get("slot"),
                    "status": str(slot.get("status") or "queued").lower(),
                    "message": slot.get("message"),
                    "started_at": slot.get("started_at"),
                    "ended_at": slot.get("ended_at"),
                    "files": slot.get("files") or [],
                }
            )
        normalized = {
            "box": box,
            "run_id": run_id,
            "status": status,
            "started_at": payload.get("started_at"),
            "ended_at": payload.get("ended_at"),
            "progress_pct": progress_pct,
            "remaining_s": remaining_s,
            "slots": slots,
            "mode": payload.get("mode"),
        }
        return normalized

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
        data = JobRestAdapter._json_any(resp)
        if not isinstance(data, dict):
            raise RuntimeError("Invalid JSON response: expected object")
        return data

    @staticmethod
    def _json_any(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            txt = getattr(resp, "text", "")[:400]
            raise RuntimeError(f"Invalid JSON response: {txt}")
