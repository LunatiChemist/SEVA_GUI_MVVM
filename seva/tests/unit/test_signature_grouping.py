import json
from seva.usecases.start_experiment_batch import _derive_mode, _normalize_params


def test_derive_mode_single_flag():
    snap = {"run_cv": "1", "run_dc": "0"}
    assert _derive_mode(snap) == "CV"


def test_derive_mode_raises_on_multiple():
    import pytest

    with pytest.raises(Exception):
        _derive_mode({"run_cv": "1", "run_dc": "1"})


def test_normalize_params_strips_flags():
    snap = {"run_dc": "1", "ea.duration_s": "10", "foo": "bar"}
    params = _normalize_params("DC", snap)
    assert (
        "run_dc" not in params
        and params["ea.duration_s"] == "10"
        and params["foo"] == "bar"
    )
