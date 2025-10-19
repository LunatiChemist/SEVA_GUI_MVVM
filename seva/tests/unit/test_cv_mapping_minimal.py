from seva.domain.params import CVParams


def test_cv_params_payload_casts_numeric_fields():
    snapshot = {
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.4",
        "cv.final_v": "1.2",
        "cv.scan_rate_v_s": "0.25",
        "cv.cycles": "3",
        "foo": "bar",
        "run_cv": "1",
    }

    params = CVParams.from_form(snapshot)
    payload = params.to_payload()

    assert set(payload.keys()) == {"start", "vertex1", "vertex2", "end", "scan_rate", "cycles"}
    assert payload["start"] == 0.0
    assert payload["vertex1"] == 0.5
    assert payload["vertex2"] == -0.4
    assert payload["end"] == 1.2
    assert payload["scan_rate"] == 0.25
    assert payload["cycles"] == 3



def test_cv_params_preserves_invalid_values():
    snapshot = {
        "cv.vertex1_v": "bad-value",
        "cv.vertex2_v": "0.0",
        "cv.final_v": "",
        "cv.scan_rate_v_s": "abc",
        "cv.cycles": "oops",
        "cv.start_v": " 1.5 ",
    }

    params = CVParams.from_form(snapshot)
    payload = params.to_payload()

    assert payload["start"] == 1.5
    assert payload["vertex1"] == "bad-value"
    assert payload["vertex2"] == 0.0
    assert payload["end"] == ""
    assert payload["scan_rate"] == "abc"
    assert payload["cycles"] == "oops"
