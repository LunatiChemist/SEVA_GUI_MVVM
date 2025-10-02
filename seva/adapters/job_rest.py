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
      - GET  {base}/jobs/{run_id}      -> {"run_id": "...", "started_at": "...", "finished_at": null,
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

    def start_batch(self, plan: Dict) -> Tuple[RunGroupId, Dict[BoxId, str]]:
        selection: Iterable[str] = plan.get("selection") or []
        selection = list(selection)
        if not selection:
            raise ValueError("start_batch: empty selection")

        # Group selection by box → slots via registry lookup
        per_box_slots: Dict[BoxId, List[int]] = {}
        for wid in selection:
            tpl = self.well_to_slot.get(wid)
            if not tpl:
                raise ValueError(
                    f"Unknown well id '{wid}' for configured boxes {self.box_order}"
                )
            box, slot = tpl
            per_box_slots.setdefault(box, [])
            if slot not in per_box_slots[box]:
                per_box_slots[box].append(slot)

        group_id: RunGroupId = plan.get("group_id") or str(uuid4())
        mode = (
            plan.get("mode") or plan.get("electrode_mode") or "CV"
        )  # tolerate older field name
        params = plan.get("params") or {}

        run_ids: Dict[BoxId, str] = {}
        for box, slots in per_box_slots.items():
            url = self._make_url(box, "/jobs")
            payload = {"devices": sorted(slots), "mode": mode, "params": params}
            resp = self.sessions[box].post(
                url, json_body=payload, timeout=self.cfg.request_timeout_s
            )
            self._ensure_ok(resp, f"start[{box}]")
            data = self._json(resp)
            run_id = str(data.get("run_id") or f"{box}-{group_id[:8]}")
            run_ids[box] = run_id

        self._groups[group_id] = run_ids
        return group_id, dict(run_ids)

    def cancel_group(self, run_group_id: RunGroupId) -> None:
        print("Cancel not implemented on API side.")

    def poll_group(self, run_group_id: RunGroupId) -> Dict:
        """Return a RAW normalized snapshot with times & channel states (no % here)."""
        mapping = self._groups.get(run_group_id, {})
        snapshot = {"boxes": {}, "wells": [], "activity": {}}

        for box, run_id in mapping.items():
            url = self._make_url(box, f"/jobs/{run_id}")
            resp = self.sessions[box].get(url, timeout=self.cfg.request_timeout_s)
            if resp.status_code == 404:
                snapshot["boxes"][box] = {
                    "phase": "Idle",
                    "started_at": None,
                    "finished_at": None,
                    "subrun": None,
                }
                continue

            self._ensure_ok(resp, f"status[{box}]")
            data = self._json(resp)

            started_at = data.get("started_at")
            finished_at = data.get("finished_at")
            phase = "Done" if finished_at else ("Running" if started_at else "Queued")
            subrun = str(data.get("run_id") or run_id)

            snapshot["boxes"][box] = {
                "phase": phase,
                "started_at": started_at,
                "finished_at": finished_at,
                "subrun": subrun,
            }

            channels = data.get("channels") or data.get("wells") or []
            for ch in channels:
                slot = int(ch.get("slot") or ch.get("channel") or ch.get("index") or 0)
                if not (1 <= slot <= 10):
                    continue  # ignore weird channel entries
                wid = self.slot_to_well.get((box, slot))
                if not wid:
                    continue
                state = str(ch.get("state") or ch.get("phase") or "Unknown")
                werr = str(ch.get("error") or "")
                # progress value left as 0; UseCase will compute % if duration known
                snapshot["wells"].append((wid, state, 0, werr, subrun))
                snapshot["activity"][wid] = state

        return snapshot

    def download_group_zip(self, run_group_id: RunGroupId, target_dir: str) -> str:
        mapping = self._groups.get(run_group_id, {})
        out_dir = os.path.join(target_dir, str(run_group_id))
        os.makedirs(out_dir, exist_ok=True)

        for box, run_id in mapping.items():
            url = self._make_url(box, f"/runs/{run_id}/zip")
            resp = self.sessions[box].get(
                url,
                timeout=self.cfg.download_timeout_s,
                stream=True,
                accept="application/zip",
            )
            if resp.status_code == 404:
                continue
            self._ensure_ok(resp, f"download[{box}]")

            path = os.path.join(out_dir, f"{run_group_id}_{box}.zip")
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
