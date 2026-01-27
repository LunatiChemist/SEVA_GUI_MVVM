from __future__ import annotations

from seva.domain.modes import ModeRegistry
from seva.domain.params import CVParams


def test_mode_registry_default_rules() -> None:
    registry = ModeRegistry.default()
    assert registry.label_for("DCAC") == "DC/AC"
    assert registry.builder_for("CV") is CVParams

    fields = {
        "cv.start_v": "0.1",
        "run_cv": "1",
        "ea.duration_s": "5",
    }
    snapshot = registry.filter_fields("CV", fields)
    assert "cv.start_v" in snapshot
    assert snapshot["run_cv"] == "1"
    assert "ea.duration_s" not in snapshot
