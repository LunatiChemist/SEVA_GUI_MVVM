from seva.usecases.start_experiment_batch import StartExperimentBatch
from seva.domain.ports import JobPort


class _JobMock:
    def start_batch(self, plan):
        return ("group-1", {"A": "A-1"})


def test_start_experiment_batch_happy_path():
    uc = StartExperimentBatch(job_port=_JobMock())
    run_id, sub = uc({})
    assert run_id == "group-1"
    assert sub["A"] == "A-1"
