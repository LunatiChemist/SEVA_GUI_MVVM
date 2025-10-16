from __future__ import annotations

import sys
import types
from typing import Any, Dict, List, Optional


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


class _ResponseStub:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload


class _SessionStub:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def post(
        self, url: str, *, json_body: Optional[Dict[str, Any]] = None, timeout: int
    ):
        self.calls.append({"url": url, "json": json_body, "timeout": timeout})
        return _ResponseStub({"run_id": "run-123"})


def test_adapter_body_includes_metadata():
    adapter = JobRestAdapter(base_urls={"A": "https://example.test"})
    session_stub = _SessionStub()
    adapter.sessions["A"] = session_stub

    plan = {
        "group_id": "group-1",
        "jobs": [
            {
                "box": "A",
                "wells": ["A1"],
                "mode": "CV",
                "params": {"start": 0.0},
                "tia_gain": None,
                "sampling_interval": None,
                "make_plot": False,
                "experiment_name": "Experiment Alpha",
                "subdir": "Batch 001",
                "client_datetime": "2024-03-05_10-15-30",
            }
        ],
    }

    group_id, per_box_runs = adapter.start_batch(plan)

    assert group_id == "group-1"
    assert per_box_runs == {"A": ["run-123"]}

    assert len(session_stub.calls) == 1
    call = session_stub.calls[0]
    payload = call["json"]
    assert payload["devices"] == ["slot01"]
    assert payload["experiment_name"] == "Experiment Alpha"
    assert payload["subdir"] == "Batch 001"
    assert payload["client_datetime"] == "2024-03-05_10-15-30"
    assert "run_name" not in payload
    assert "folder_name" not in payload


def test_job_rest_payload_passes_through_meta_values():
    adapter = JobRestAdapter(base_urls={"A": "https://example.test"})
    session_stub = _SessionStub()
    adapter.sessions["A"] = session_stub

    raw_subdir = "  nested/dir  "
    raw_name = " Experiment Alpha "
    raw_client_dt = "2024/03/05 10:15:30"

    plan = {
        "group_id": "group-2",
        "jobs": [
            {
                "box": "A",
                "wells": ["A1"],
                "mode": "CV",
                "params": {},
                "make_plot": True,
                "experiment_name": raw_name,
                "subdir": raw_subdir,
                "client_datetime": raw_client_dt,
            }
        ],
    }

    adapter.start_batch(plan)

    assert len(session_stub.calls) == 1
    payload = session_stub.calls[0]["json"]
    assert payload["experiment_name"] == "Experiment Alpha"
    assert payload["subdir"] == "nested/dir"
    assert payload["client_datetime"] == "2024/03/05 10:15:30"
