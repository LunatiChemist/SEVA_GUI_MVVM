import sys
import types


class _RequestsStub(types.ModuleType):
    class Response:  # minimal stub for type annotations
        def __init__(self, status_code: int = 200):
            self.status_code = status_code

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):  # pragma: no cover - unused in tests
            raise NotImplementedError

        def post(self, *args, **kwargs):  # pragma: no cover - unused in tests
            raise NotImplementedError


sys.modules.setdefault("requests", _RequestsStub("requests"))

from seva.adapters.job_rest import JobRestAdapter


class _DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _DummySession:
    def __init__(self, responses, *, allow_get=False):
        self.responses = responses
        self.calls = []
        self.allow_get = allow_get

    def post(self, url, *, json_body=None, timeout=None):
        self.calls.append({"url": url, "body": json_body, "timeout": timeout})
        run_ids = tuple((json_body or {}).get("run_ids", []))
        payload = self.responses.get(run_ids, [])
        return _DummyResponse(payload)

    def get(self, *args, **kwargs):
        if self.allow_get:
            return _DummyResponse({}, status_code=404)
        raise AssertionError("GET should not be called during bulk polling")


def _adapter_with_group(run_snapshots):
    adapter = JobRestAdapter(base_urls={"A": "http://box-a"})
    adapter._groups = {"grp": {"A": [snap["run_id"] for snap in run_snapshots]}}
    for snap in run_snapshots:
        adapter._store_run_snapshot(snap)
    return adapter


def test_poll_group_filters_pending_run_ids():
    run_snapshots = [
        {
            "box": "A",
            "run_id": "run-1",
            "status": "done",
            "started_at": None,
            "ended_at": None,
            "progress_pct": 100,
            "remaining_s": 0,
            "slots": [],
            "mode": None,
        },
        {
            "box": "A",
            "run_id": "run-2",
            "status": "running",
            "started_at": None,
            "ended_at": None,
            "progress_pct": 45,
            "remaining_s": 180,
            "slots": [],
            "mode": None,
        },
    ]
    adapter = _adapter_with_group(run_snapshots)

    responses = {
        ("run-2",): [
            {
                "run_id": "run-2",
                "status": "running",
                "progress_pct": 55,
                "remaining_s": 120,
                "slots": [],
            }
        ]
    }
    session = _DummySession(responses)
    adapter.sessions["A"] = session

    snapshot = adapter.poll_group("grp")

    assert session.calls and session.calls[0]["body"] == {"run_ids": ["run-2"]}
    runs = snapshot["boxes"]["A"]["runs"]
    assert runs[0]["progress_pct"] == 100
    assert runs[1]["progress_pct"] == 55
    assert snapshot["all_done"] is False


def test_poll_group_marks_all_done_without_additional_calls():
    run_snapshots = [
        {
            "box": "A",
            "run_id": "run-1",
            "status": "done",
            "started_at": None,
            "ended_at": None,
            "progress_pct": 100,
            "remaining_s": 0,
            "slots": [],
            "mode": None,
        },
        {
            "box": "A",
            "run_id": "run-2",
            "status": "failed",
            "started_at": None,
            "ended_at": None,
            "progress_pct": 100,
            "remaining_s": 0,
            "slots": [],
            "mode": None,
        },
    ]
    adapter = _adapter_with_group(run_snapshots)
    session = _DummySession({}, allow_get=False)
    adapter.sessions["A"] = session

    snapshot = adapter.poll_group("grp")

    assert session.calls == []
    assert snapshot["all_done"] is True
    assert all(run["status"] in {"done", "failed"} for run in snapshot["boxes"]["A"]["runs"])
