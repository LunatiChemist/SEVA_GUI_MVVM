from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_ROOT = PROJECT_ROOT / "seva"
EXCLUDED_CLIENT_FILES = {
    CLIENT_ROOT / "adapters" / "job_rest_mock.py",
}
EXCLUDED_CLIENT_DIRS = {
    CLIENT_ROOT / "tests",
}


def _is_within(path: Path, target: Path) -> bool:
    try:
        path.relative_to(target)
        return True
    except ValueError:
        return False


def iter_client_python_files() -> list[Path]:
    python_files = []
    for file_path in CLIENT_ROOT.rglob("*.py"):
        if any(_is_within(file_path, excluded) for excluded in EXCLUDED_CLIENT_DIRS):
            continue
        if file_path in EXCLUDED_CLIENT_FILES:
            continue
        python_files.append(file_path)
    return python_files


def find_needle(needle: str, files: list[Path]) -> list[str]:
    matches: list[str] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        if needle not in text:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                rel_path = file_path.relative_to(PROJECT_ROOT)
                matches.append(f"{rel_path}:{line_no}: {line.strip()}")
    return matches


@pytest.mark.parametrize(
    "needle",
    [
        "RunStorageInfo",
        "group_registry",
        "planned_duration",
    ],
)
def test_client_code_has_no_legacy_symbols(needle: str) -> None:
    files = iter_client_python_files()
    matches = find_needle(needle, files)
    assert not matches, f"Legacy symbol '{needle}' reintroduced:\n" + "\n".join(matches)


def test_client_has_no_run_or_folder_name_builders() -> None:
    needles = [
        "build_run_name",
        "build_folder_name",
        "run_name_builder",
        "folder_name_builder",
        "RunNameBuilder",
        "FolderNameBuilder",
    ]
    files = iter_client_python_files()
    matches = []
    for needle in needles:
        matches.extend(find_needle(needle, files))
    assert not matches, "Run/folder name builder logic must not exist in the client:\n" + "\n".join(matches)


@pytest.mark.parametrize(
    "relative",
    [
        ("adapters",),
        ("usecases",),
        ("app", "views"),
    ],
)
def test_client_storage_usecases_views_do_not_reference_csv(relative: tuple[str, ...]) -> None:
    directory = CLIENT_ROOT.joinpath(*relative)
    if not directory.exists():
        pytest.skip(f"Directory '{directory}' missing; adjust test if structure changes.")

    files = [
        file_path
        for file_path in directory.rglob("*.py")
        if not any(_is_within(file_path, excluded) for excluded in EXCLUDED_CLIENT_DIRS)
    ]
    matches = find_needle(".csv", files)
    assert not matches, "CSV handling must not be implemented in client adapters/usecases/views:\n" + "\n".join(matches)
