# seva/adapters/job_rest.py
from __future__ import annotations

import logging
import os
from datetime import timezone
from typing import Dict, Iterable, Tuple, Optional, Any, List, Set
from uuid import uuid4

import requests

# Domain Port
from seva.domain.entities import ExperimentPlan
from seva.domain.util import normalize_mode_name
from seva.domain.ports import JobPort, RunGroupId, BoxId

from .http_client import HttpConfig, RetryingSession
from .api_errors import (
    ApiClientError,
    ApiError,
    ApiServerError,
    build_error_message,
    extract_error_code,
    extract_error_hint,
    parse_error_payload,
)


class JobRestAdapter(JobPort):
    """REST adapter for your FastAPI boxes.

    Endpoints:
      - POST {base}/jobs               body: {"devices":["slot01"], "modes":["CV"], "params_by_mode":{...}}
              -> {"run_id": "..."}
      - POST {base}/jobs/status        -> [{"run_id":"...", "status":"running", ...}]
      - GET  {base}/runs/{run_id}/zip  -> application/zip

    Notes:
      - Cancel: POST /jobs/{run_id}/cancel per run.
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
        self._log = logging.getLogger(__name__)
        self.base_urls = dict(base_urls)
        self.api_keys = dict(api_keys or {})
        self.cfg = HttpConfig(
            request_timeout_s=request_timeout_s,
            download_timeout_s=download_timeout_s,
            retries=retries,
        )
        # Dynamic, alphabetic box order
        self.box_order: List[BoxId] = sorted(self.base_urls.keys())

        # Sessions per box
        self.sessions: Dict[BoxId, RetryingSession] = {
            b: RetryingSession(self.api_keys.get(b), self.cfg)
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
        """Build well_id <-> (box, slot) mapping using fixed box-local offsets.

        Offsets per box letter: A:+0, B:+10, C:+20, D:+30. The well number is
        `offset + slot_index` (slot_index is 1-based). Examples:
        - slot01 on box A -> well A1
        - slot01 on box B -> well B11
        - slot10 on box D -> well D40
        """
        offsets = {"A": 0, "B": 10, "C": 20, "D": 30}
        self.well_to_slot.clear()
        self.slot_to_well.clear()
        for box in self.box_order:
            box_letter = str(box)[:1].upper()
            if box_letter not in offsets:
                raise ValueError(f"Unsupported box id '{box}': expected leading letter in {sorted(offsets)}")
            offset = offsets[box_letter]
            for slot in range(1, 11):
                well_number = offset + slot
                well_id = f"{box}{well_number}"
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

    def start_batch(self, plan: ExperimentPlan) -> Tuple[RunGroupId, Dict[BoxId, List[str]]]:
        if not isinstance(plan, ExperimentPlan):
            raise TypeError(f"start_batch expects ExperimentPlan, got {type(plan).__name__}")

        meta = plan.meta
        client_dt = (
            meta.client_dt.value.astimezone(timezone.utc)
            .replace(microsecond=0)
        )
        client_dt_text = client_dt.isoformat()
        if client_dt_text.endswith("+00:00"):
            client_dt_text = client_dt_text[:-6] + "Z"

        group_id = str(meta.group_id) if str(meta.group_id).strip() else str(uuid4())
        experiment_name = (meta.experiment or "").strip()
        if not experiment_name:
            raise ValueError("start_batch: missing experiment_name in plan meta")
        subdir = (meta.subdir or "").strip() or None

        run_ids: Dict[BoxId, List[str]] = {}
        self._groups[group_id] = {}

        if not plan.wells:
            raise ValueError("start_batch: plan contains no wells")

        for well_plan in plan.wells:
            normalized_modes = [
                normalized for mode in (well_plan.modes or [])
                if (normalized := normalize_mode_name(mode))
            ]
            well_id = str(well_plan.well)
            if not well_id:
                raise ValueError("Experiment plan contains an empty well identifier.")

            slot_info = self.well_to_slot.get(well_id)
            if not slot_info:
                raise ValueError(f"Unknown well '{well_id}' for any configured box.")
            box, slot = slot_info
            devices = [self._slot_label(slot)]

            params_by_mode: Dict[str, Dict[str, Any]] = {}
            for mode_name, params_obj in (well_plan.params_by_mode or {}).items():
                mode_key = str(mode_name)
                try:
                    params_by_mode[mode_key] = params_obj.to_payload()
                except NotImplementedError as exc:  # pragma: no cover
                    raise ValueError(
                        f"Well '{well_id}' mode '{mode_name}' parameters do not support payload serialization."
                    ) from exc
                except AttributeError as exc:  # pragma: no cover
                    raise ValueError(
                        f"Well '{well_id}' mode '{mode_name}' parameters are missing a to_payload() method."
                    ) from exc

            payload = {
                "devices": devices,
                "modes": normalized_modes,
                "params_by_mode": params_by_mode,
                "tia_gain": meta.tia_gain,
                "sampling_interval": meta.sampling_interval,
                "make_plot": bool(meta.make_plot),
                "experiment_name": experiment_name,
                "subdir": subdir,
                "group_id": group_id,
                "client_datetime": client_dt_text,
            }

            url = self._make_url(box, "/jobs")
            if self._log.isEnabledFor(logging.DEBUG):
                self._log.debug(
                    "POST start[%s]: well=%s devices=%s modes=%s group=%s",
                    box, well_id, devices, payload["modes"], group_id,
                )
            session = self.sessions.get(box)
            if session is None:
                raise ApiError(f"No HTTP session configured for box '{box}'", context=f"start[{box}]")
            resp = session.post(url, json_body=payload, timeout=self.cfg.request_timeout_s)

            self._ensure_ok(resp, f"start[{box}]")
            data = self._json(resp)
            run_id_raw = data.get("run_id")
            if not run_id_raw:
                raise ApiError("Response payload missing run_id", context=f"start[{box}]", payload=data)
            run_id = str(run_id_raw)

            self._groups[group_id].setdefault(box, []).append(run_id)
            run_ids.setdefault(box, []).append(run_id)

            normalized = self._normalize_job_status(box, data)
            self._store_run_snapshot(normalized)

        return group_id, run_ids

    def cancel_run(self, box_id: BoxId, run_id: str) -> None:
        session = self.sessions.get(box_id)
        if session is None:
            raise ApiError(
                f"No session configured for box '{box_id}'",
                context=f"cancel[{box_id}:{run_id}]",
            )
        self._cancel_run_with_session(session, box_id, run_id, ignore_missing=False)

    def cancel_runs(self, box_to_run_ids: Dict[BoxId, List[str]]) -> None:
        if not box_to_run_ids:
            return
        for box, run_ids in box_to_run_ids.items():
            if not run_ids:
                continue
            session = self.sessions.get(box)
            if session is None:
                raise ApiError(
                    f"No session configured for box '{box}'",
                    context=f"cancel[{box}:*]",
                )
            seen: Set[str] = set()
            for run_id in run_ids:
                run_id_str = str(run_id or "").strip()
                if not run_id_str or run_id_str in seen:
                    continue
                seen.add(run_id_str)
                self._cancel_run_with_session(
                    session, box, run_id_str, ignore_missing=False
                )

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        self._log.info("Cancel group %s requested.", run_group_id)
        box_runs = self._groups.get(run_group_id, {})
        if not box_runs:
            return
        for box, runs in box_runs.items():
            session = self.sessions.get(box)
            if session is None:
                self._log.warning(
                    "Cancel group %s: no session configured for box %s",
                    run_group_id,
                    box,
                )
                continue
            for run_id in runs:
                self._cancel_run_with_session(session, box, run_id, ignore_missing=True)

    def _cancel_run_with_session(
        self,
        session: RetryingSession,
        box: BoxId,
        run_id: str,
        *,
        ignore_missing: bool,
    ) -> None:
        url = self._make_url(box, f"/jobs/{run_id}/cancel")
        try:
            resp = session.post(url, timeout=self.cfg.request_timeout_s)
        except Exception as exc:
            raise ApiError(str(exc), context=f"cancel[{box}:{run_id}]") from exc
        if resp.status_code == 404 and ignore_missing:
            self._log.info(
                "Cancel run %s: already gone on box %s.", run_id, box
            )
            return
        self._ensure_ok(resp, f"cancel[{box}:{run_id}]")

    def poll_group(self, run_group_id: RunGroupId) -> Dict:
        """Bulk poll run snapshots using POST /jobs/status and cached terminals."""
        box_runs: Dict[BoxId, List[str]] = self._groups.get(run_group_id, {}) or {}
        if not box_runs:
            recovered = self._recover_group_runs(run_group_id)
            if recovered:
                self._groups[run_group_id] = recovered
                box_runs = recovered
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
                self._log.debug(
                    "Poll group %s: box=%s pending_ids=%d",
                    run_group_id,
                    box,
                    len(pending_ids),
                )
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
                    "current_mode": data.get("current_mode") or data.get("mode"),
                    "remaining_modes": data.get("remaining_modes") or [],
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
                        {
                            "well": wid,
                            "phase": s_status,  # UI-kompatibles Label (Queued/Running/Done/Error)
                            "progress_pct": data.get("progress_pct", 0),
                            "remaining_s": data.get("remaining_s"),
                            "error": s_msg,
                            "run_id": run_entry["run_id"],
                            # NEU: Modi
                            "current_mode": data.get("current_mode") or data.get("mode"),
                            "remaining_modes": data.get("remaining_modes") or [],
                        }
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

    def _recover_group_runs(self, run_group_id: RunGroupId) -> Dict[BoxId, List[str]]:
        recovered: Dict[BoxId, List[str]] = {}
        group_text = str(run_group_id or "").strip()
        if not group_text:
            return recovered
        for box in self.box_order:
            session = self.sessions.get(box)
            if session is None:
                continue
            url = self._make_url(box, f"/jobs?group_id={group_text}")
            resp = session.get(url, timeout=self.cfg.request_timeout_s)
            self._ensure_ok(resp, f"jobs[{box}]")
            payload = self._json_any(resp)
            if not isinstance(payload, list):
                raise RuntimeError("Invalid JSON response: expected list of jobs")
            run_ids: List[str] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                run_id_raw = item.get("run_id")
                if not run_id_raw:
                    continue
                run_id = str(run_id_raw)
                if run_id and run_id not in run_ids:
                    run_ids.append(run_id)
            if run_ids:
                recovered[box] = run_ids
        if recovered and self._log.isEnabledFor(logging.DEBUG):
            self._log.debug("Recovered group %s runs=%s", run_group_id, recovered)
        return recovered

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
        self, box: BoxId, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid job status payload: expected object")
        run_id_raw = payload.get("run_id")
        if not run_id_raw:
            raise RuntimeError("Job status payload missing run_id")
        run_id = str(run_id_raw)
        status = str(payload.get("status") or "queued").lower() or "queued"
        slots = payload.get("slots") or []
        current_mode = payload.get("current_mode") or payload.get("mode")
        normalized = {
            "box": box,
            "run_id": run_id,
            "status": status,
            "started_at": payload.get("started_at"),
            "ended_at": payload.get("ended_at"),
            "progress_pct": payload.get("progress_pct") or 0,
            "remaining_s": payload.get("remaining_s"),
            "slots": slots,
            "mode": current_mode,
            "current_mode": current_mode,
            "modes": payload.get("modes") or [],
            "remaining_modes": payload.get("remaining_modes") or [],
        }
        return normalized

    @staticmethod
    def _ensure_ok(resp: requests.Response, ctx: str) -> None:
        if 200 <= resp.status_code < 300:
            return
        status = resp.status_code
        payload = parse_error_payload(resp)
        message = build_error_message(ctx, status, payload)
        code = extract_error_code(payload)
        hint = extract_error_hint(payload)
        if 400 <= status < 500:
            raise ApiClientError(
                message,
                status=status,
                code=code,
                hint=hint,
                payload=payload,
                context=ctx,
            )
        if 500 <= status < 600:
            raise ApiServerError(
                message,
                status=status,
                payload=payload,
                context=ctx,
            )
        raise ApiError(message, status=status, payload=payload, context=ctx)

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
