from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from typing import Any, Dict, List

if "requests" not in sys.modules:
    class _RequestsSessionStub:
        def get(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP GET not supported in tests without requests")

        def post(self, *args, **kwargs):  # pragma: no cover
            raise RuntimeError("HTTP POST not supported in tests without requests")

    class _RequestsExceptionsStub:
        Timeout = RuntimeError
        ConnectionError = RuntimeError
        RequestException = RuntimeError

    sys.modules["requests"] = types.SimpleNamespace(
        Session=_RequestsSessionStub,
        Response=object,
        exceptions=_RequestsExceptionsStub,
    )

from seva.adapters.job_rest import JobRestAdapter
from seva.domain.entities import (
    ClientDateTime,
    ExperimentPlan,
    GroupId,
    ModeName,
    PlanMeta,
    WellId,
    WellPlan,
)
from seva.domain.params import CVParams


class _SessionStub:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._idx = 0

    def post(self, url: str, *, json_body: Dict[str, Any], timeout: int):
        self._idx += 1
        run_id = f"run-{self._idx}"
        self.calls.append({"url": url, "json": json_body, "timeout": timeout})
        return types.SimpleNamespace(status_code=200, json=lambda: {"run_id": run_id})


def _plan() -> ExperimentPlan:
    meta = PlanMeta(
        experiment="Experiment Alpha",
        subdir="Batch 001",
        client_dt=ClientDateTime(datetime(2024, 3, 5, 10, 15, 30, tzinfo=timezone.utc)),
        group_id=GroupId("grp-001"),
    )
    snapshot = {
        "run_cv": "1",
        "cv.start_v": "0",
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.5",
        "cv.final_v": "0",
        "cv.scan_rate_v_s": "0.1",
        "cv.cycles": "2",
    }
    params = CVParams.from_form(snapshot)
    wells = [
        WellPlan(well=WellId("A1"), mode=ModeName("CV"), params=params),
        WellPlan(well=WellId("B2"), mode=ModeName("CV"), params=params),
    ]
    return ExperimentPlan(meta=meta, wells=wells, make_plot=False)


def test_start_batch_posts_jobs_per_well() -> None:
    adapter = JobRestAdapter(base_urls={"A": "http://box-a", "B": "http://box-b"})
    adapter.well_to_slot = {"A1": ("A", 1), "B2": ("B", 2)}
    adapter.sessions = {"A": _SessionStub(), "B": _SessionStub()}

    group_id, per_box_runs = adapter.start_batch(_plan())

    assert group_id == "grp-001"
    assert per_box_runs == {"A": ["run-1"], "B": ["run-1"]}

    for box, session in adapter.sessions.items():
        assert len(session.calls) == 1
        call = session.calls[0]
        assert call["url"].endswith("/jobs")
        assert call["json"]["modes"] == ["CV"]
        assert call["json"]["experiment_name"] == "Experiment Alpha"
        assert call["json"]["client_datetime"] == "2024-03-05T10:15:30Z"
        expected_slot = "slot01" if box == "A" else "slot02"
        assert call["json"]["devices"] == [expected_slot]
