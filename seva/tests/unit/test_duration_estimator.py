from seva.usecases.start_experiment_batch import _estimate_planned_duration


def test_dc_duration_primary():
    p = {"ea.duration_s": "30"}
    assert _estimate_planned_duration("DC", p) >= 30


def test_dc_duration_from_charge():
    p = {"ea.charge_cutoff_c": "30", "ea.target_ma": "10", "control_mode": "current"}
    dur = _estimate_planned_duration("DC", p)
    assert dur and dur >= 3000 / 100 + 1  # 30C / 0.01A + buffer ~ 3000s


def test_cv_duration_basic():
    p = {
        "cv.vertex1_v": "-0.5",
        "cv.vertex2_v": "0.5",
        "cv.scan_rate_v_s": "0.1",
        "cv.cycles": "2",
    }
    assert _estimate_planned_duration("CV", p) > 0
