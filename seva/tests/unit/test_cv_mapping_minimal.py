from seva.usecases.start_experiment_batch import map_params


def test_cv_mapping_minimal_fields_and_casting():
    snapshot = {
        "cv.vertex1_v": "0.5",
        "cv.vertex2_v": "-0.4",
        "cv.final_v": "1.2",
        "cv.scan_rate_v_s": "0.25",
        "cv.cycles": "3",
        "foo": "bar",
        "run_cv": "1",
    }

    mapped = map_params("CV", snapshot)

    assert set(mapped.keys()) == {
        "start",
        "vertex1",
        "vertex2",
        "end",
        "scan_rate",
        "cycles",
    }
    assert mapped["start"] == 0.0
    assert mapped["vertex1"] == 0.5
    assert mapped["vertex2"] == -0.4
    assert mapped["end"] == 1.2
    assert mapped["scan_rate"] == 0.25
    assert mapped["cycles"] == 3


def test_cv_mapping_best_effort_casting_preserves_invalid_values():
    snapshot = {
        "cv.vertex1_v": "bad-value",
        "cv.vertex2_v": "0.0",
        "cv.final_v": "",
        "cv.scan_rate_v_s": "abc",
        "cv.cycles": "oops",
        "cv.start_v": " 1.5 ",
    }

    mapped = map_params("CV", snapshot)

    assert mapped["start"] == 1.5
    assert mapped["vertex1"] == "bad-value"
    assert mapped["vertex2"] == 0.0
    assert mapped["end"] == ""
    assert mapped["scan_rate"] == "abc"
    assert mapped["cycles"] == "oops"
