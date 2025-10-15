import os

from seva.utils.download_paths import (
    build_group_root,
    build_zip_paths,
    collect_box_runs,
)


def test_collect_box_runs_uses_snapshot_fallback():
    explicit = {}
    snapshot = {
        "A": {"runs": [{"run_id": "run-1"}, {"run_id": ""}, {"run_id": None}]},
        "B": {"runs": [{"run_id": "run-2"}]},
    }

    collected = collect_box_runs(explicit, snapshot)

    assert collected == {"A": ["run-1"], "B": ["run-2"]}


def test_build_zip_paths_returns_absolute(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    box_runs = {"B": ["run-2"], "A": ["run-1", "run-3"]}

    paths = build_zip_paths(str(results_dir), "group-1", box_runs)

    expected = [
        os.path.abspath(results_dir / "group-1" / "A" / "run-1.zip"),
        os.path.abspath(results_dir / "group-1" / "A" / "run-3.zip"),
        os.path.abspath(results_dir / "group-1" / "B" / "run-2.zip"),
    ]
    assert paths == expected


def test_build_group_root_without_subdir(tmp_path):
    root = build_group_root(
        str(tmp_path / "results"),
        experiment_name="Experiment Alpha",
        client_datetime="2024-03-05T10:15:30",
    )

    expected = os.path.abspath(
        tmp_path / "results" / "Experiment_Alpha" / "2024-03-05T10-15-30"
    )
    assert root == expected


def test_build_group_root_with_subdir(tmp_path):
    root = build_group_root(
        str(tmp_path / "results"),
        experiment_name="Experiment Beta",
        client_datetime="2024-03-05 13:00:00",
        subdir="Batch #01",
    )

    expected = os.path.abspath(
        tmp_path
        / "results"
        / "Experiment_Beta"
        / "Batch_01"
        / "2024-03-05_13-00-00"
    )
    assert root == expected
