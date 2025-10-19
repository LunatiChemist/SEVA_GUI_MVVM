from seva.domain.params import CVParams


def test_cv_params_roundtrip_from_form_to_payload():
    form = {
        "cv.start_v": "",
        "cv.vertex1_v": "0.45",
        "cv.vertex2_v": "-0.30",
        "cv.final_v": "0.10",
        "cv.scan_rate_v_s": "0.25",
        "cv.cycles": "3",
        "run_cv": "1",
        "run_eis": "0",
    }

    params = CVParams.from_form(form)
    payload = params.to_payload()

    assert payload == {
        "start": 0.0,
        "vertex1": 0.45,
        "vertex2": -0.30,
        "end": 0.10,
        "scan_rate": 0.25,
        "cycles": 3,
    }
    assert isinstance(payload["start"], float)
    assert isinstance(payload["vertex1"], float)
    assert isinstance(payload["vertex2"], float)
    assert isinstance(payload["scan_rate"], float)
    assert isinstance(payload["cycles"], int)
    assert params.flags["run_cv"] == "1"
    assert params.flags["run_eis"] == "0"


def test_cv_params_preserves_invalid_inputs_and_flags():
    form = {
        "cv.vertex1_v": "bad-value",
        "cv.vertex2_v": "0.0",
        "cv.final_v": " ",
        "cv.scan_rate_v_s": "slow",
        "cv.cycles": "oops",
        "flags": {"run_cv": "1"},
    }

    params = CVParams.from_form(form)
    payload = params.to_payload()

    assert payload["start"] == 0.0
    assert payload["vertex1"] == "bad-value"
    assert payload["vertex2"] == 0.0
    assert payload["end"] == " "
    assert payload["scan_rate"] == "slow"
    assert payload["cycles"] == "oops"
    assert params.flags["run_cv"] == "1"
