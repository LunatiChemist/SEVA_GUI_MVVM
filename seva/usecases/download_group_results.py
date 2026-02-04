"""Use case for downloading and normalizing run-group artifacts.

The workflow downloads ZIP archives via `JobPort`, extracts files, maps slot
folders to well identifiers, and optionally cleans up source archives.
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Tuple

from ..domain.mapping import normalize_slot_registry, resolve_well_id
from ..domain.ports import JobPort, RunGroupId, UseCaseError
from ..usecases.error_mapping import map_api_error
from ..domain.storage_meta import StorageMeta


CleanupMode = str


@dataclass
class DownloadGroupResults:
    """Use-case callable for downloading and unpacking group results.
    
    Attributes:
        Fields are consumed by use-case orchestration code and callers.
    """
    job_port: JobPort

    def __call__(
        self,
        run_group_id: RunGroupId,
        target_dir: str,
        storage_meta: Optional[StorageMeta] = None,
        *,
        cleanup: CleanupMode = "keep",
    ) -> str:
        """
        Download, unpack, and normalize result archives for a run group.

        Returns the absolute path of the extraction root
        (<results>/<experiment>/<subdir?>/<client_datetime>).
        """
        storage = self._validate_storage_meta(storage_meta)
        results_root = os.path.abspath(storage.results_dir or target_dir or ".")
        os.makedirs(results_root, exist_ok=True)

        try:
            zip_root = self.job_port.download_group_zip(run_group_id, results_root)
        except Exception as exc:
            raise map_api_error(
                exc,
                default_code="DOWNLOAD_FAILED",
                default_message="Download failed.",
            ) from exc

        zip_root = os.path.abspath(zip_root)
        if not os.path.isdir(zip_root):
            raise UseCaseError(
                "DOWNLOAD_FAILED",
                f"Adapter returned '{zip_root}', expected a directory with ZIP files.",
            )

        extraction_root = self._build_extraction_root(results_root, storage)
        os.makedirs(extraction_root, exist_ok=True)

        archives = self._collect_archives(zip_root)
        if not archives:
            raise UseCaseError(
                "NO_ARCHIVES_FOUND",
                f"No ZIP archives found for group '{run_group_id}'.",
            )

        slot_registry = self._require_slot_registry()

        for archive_path in archives:
            box = self._extract_box(zip_root, archive_path)
            box_target = os.path.join(extraction_root, box)
            os.makedirs(box_target, exist_ok=True)
            self._extract_archive(archive_path, box_target)
            self._rename_slot_dirs(box_target, box, slot_registry)

        self._cleanup_archives(zip_root, archives, cleanup)

        return extraction_root

    @staticmethod
    def _validate_storage_meta(
        storage_meta: Optional[StorageMeta]
    ) -> StorageMeta:
        if not storage_meta:
            raise UseCaseError(
                "MISSING_STORAGE_META",
                "No storage metadata available for the requested group.",
            )
        if not storage_meta.experiment.strip():
            raise UseCaseError(
                "INVALID_STORAGE_META",
                "Storage metadata missing experiment.",
            )
        if storage_meta.client_datetime is None:
            raise UseCaseError(
                "INVALID_STORAGE_META",
                "Storage metadata missing client datetime.",
            )
        return storage_meta

    @staticmethod
    def _build_extraction_root(
        results_root: str, storage: StorageMeta
    ) -> str:
        experiment = storage.experiment or ""
        subdir = storage.subdir or ""
        client_dt = storage.client_datetime_label()
        parts = [results_root, experiment]
        if subdir:
            parts.append(subdir)
        parts.append(client_dt)
        return os.path.abspath(os.path.join(*parts))

    @staticmethod
    def _collect_archives(zip_root: str) -> Iterable[str]:
        archives = []
        for dirpath, _, filenames in os.walk(zip_root):
            for name in filenames:
                if name.lower().endswith(".zip"):
                    archives.append(os.path.join(dirpath, name))
        return archives

    @staticmethod
    def _extract_box(zip_root: str, archive_path: str) -> str:
        rel_path = os.path.relpath(archive_path, zip_root)
        parts = rel_path.split(os.sep)
        if not parts:
            raise UseCaseError(
                "INVALID_ARCHIVE_LAYOUT",
                f"Archive '{archive_path}' is not placed under a box folder.",
            )
        box = parts[0]
        if not box:
            raise UseCaseError(
                "INVALID_ARCHIVE_LAYOUT",
                f"Could not determine box for archive '{archive_path}'.",
            )
        return box

    @staticmethod
    def _extract_archive(archive_path: str, dest_dir: str) -> None:
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(dest_dir)
        except zipfile.BadZipFile as exc:
            raise UseCaseError(
                "EXTRACT_FAILED", f"Archive '{archive_path}' is not a valid ZIP file."
            ) from exc
        except Exception as exc:
            raise UseCaseError(
                "EXTRACT_FAILED",
                f"Could not extract archive '{archive_path}': {exc}",
            ) from exc

    def _rename_slot_dirs(
        self,
        root: str,
        box: str,
        slot_registry: Mapping[Tuple[str, int], str],
    ) -> None:
        pattern = re.compile(r"^slot(\d{2})$", re.IGNORECASE)
        for dirpath, dirnames, _ in os.walk(root, topdown=False):
            for name in dirnames:
                match = pattern.match(name)
                if not match:
                    continue
                slot_num = int(match.group(1))
                well_id = resolve_well_id(slot_registry, box, slot_num)
                if not well_id:
                    raise UseCaseError(
                        "UNKNOWN_SLOT",
                        f"No well mapping for box '{box}' slot {slot_num:02d}.",
                    )
                if name == well_id:
                    continue
                source = os.path.join(dirpath, name)
                target = os.path.join(dirpath, well_id)
                if os.path.exists(target):
                    raise UseCaseError(
                        "RENAME_CONFLICT",
                        f"Cannot rename '{source}' to '{well_id}': destination exists.",
                    )
                os.rename(source, target)

    def _require_slot_registry(self) -> Mapping[Tuple[str, int], str]:
        registry = getattr(self.job_port, "slot_to_well", None)
        if not isinstance(registry, dict):
            raise UseCaseError(
                "MISSING_SLOT_REGISTRY",
                "Adapter does not expose slot-to-well registry.",
            )
        normalized = normalize_slot_registry(registry)
        if not normalized:
            raise UseCaseError(
                "MISSING_SLOT_REGISTRY",
                "Adapter slot registry is empty.",
            )
        return normalized

    def _cleanup_archives(
        self, zip_root: str, archives: Iterable[str], cleanup: CleanupMode
    ) -> None:
        mode = (cleanup or "keep").lower()
        if mode not in {"keep", "delete", "archive"}:
            raise UseCaseError(
                "INVALID_CLEANUP_MODE",
                f"Unsupported cleanup mode '{cleanup}'.",
            )
        archive_list = list(archives)
        if mode == "keep":
            return
        if mode == "delete":
            for path in archive_list:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise UseCaseError(
                        "CLEANUP_FAILED",
                        f"Could not delete '{path}': {exc}",
                    ) from exc
            self._prune_empty_dirs(zip_root)
            return

        # mode == "archive"
        archive_root = os.path.join(zip_root, "archive")
        for path in archive_list:
            rel = os.path.relpath(path, zip_root)
            target = os.path.join(archive_root, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            try:
                shutil.move(path, target)
            except OSError as exc:
                raise UseCaseError(
                    "CLEANUP_FAILED",
                    f"Could not archive '{path}' to '{target}': {exc}",
                ) from exc
        self._prune_empty_dirs(zip_root, preserve={archive_root})

    @staticmethod
    def _prune_empty_dirs(root: str, preserve: Optional[Iterable[str]] = None) -> None:
        preserved = {os.path.abspath(p) for p in (preserve or [])}
        root_abs = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root_abs, topdown=False):
            if dirpath in preserved:
                continue
            if dirpath == root_abs:
                continue
            if dirnames or filenames:
                continue
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
