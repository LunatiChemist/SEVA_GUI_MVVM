from __future__ import annotations

from datetime import datetime

from seva.domain.plan_builder import build_meta
from seva.usecases.build_storage_meta import BuildStorageMeta


class _Settings:
    def __init__(self, results_dir: str | None) -> None:
        self.results_dir = results_dir


def test_build_storage_meta_uses_results_dir() -> None:
    plan_meta = build_meta(
        experiment="Test",
        subdir="Sub",
        client_dt_local=datetime.now().astimezone(),
    )
    storage_meta = BuildStorageMeta()(plan_meta, _Settings("C:/data"))
    assert storage_meta.experiment == "Test"
    assert storage_meta.subdir == "Sub"
    assert storage_meta.results_dir == "C:/data"


def test_build_storage_meta_defaults_results_dir() -> None:
    plan_meta = build_meta(
        experiment="Test",
        subdir=None,
        client_dt_local=datetime.now().astimezone(),
    )
    storage_meta = BuildStorageMeta()(plan_meta, _Settings(""))
    assert storage_meta.results_dir == "."
