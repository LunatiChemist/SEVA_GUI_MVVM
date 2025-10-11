from seva.usecases.start_experiment_batch import StartExperimentBatch


class _JobMock:
    def __init__(self):
        self.last_plan = None

    def start_batch(self, plan):
        self.last_plan = plan
        return ("group-1", {"A": ["A-run-1"]})


def test_start_experiment_batch_happy_path():
    job_port = _JobMock()
    uc = StartExperimentBatch(job_port=job_port)
    plan = {
        "selection": ["A1"],
        "well_params_map": {
            "A1": {
                "run_cv": "1",
                "cv.start_v": "0",
                "cv.vertex1_v": "0.5",
                "cv.vertex2_v": "-0.5",
                "cv.final_v": "0",
                "cv.scan_rate_v_s": "0.1",
                "cv.cycles": "1",
            }
        },
        "group_id": "group-1",
    }

    run_id, sub = uc(plan)

    assert run_id == "group-1"
    assert sub["A"] == ["A-run-1"]
    assert job_port.last_plan is not None
    assert job_port.last_plan["jobs"][0]["box"] == "A"
    assert job_port.last_plan["jobs"][0]["mode"] == "CV"
