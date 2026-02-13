"""Package-update orchestration for the REST API.

This module validates update ZIP packages, manages asynchronous update jobs,
applies component payloads in deterministic order, and records audit events.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tarfile
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Callable, Dict, Iterable, Optional

SUPPORTED_COMPONENTS = ("pybeep", "rest_api", "firmware")
COMPONENT_APPLY_ORDER = ("pybeep", "rest_api", "firmware")
TERMINAL_STATUSES = {"done", "failed"}
RUNNING_STATUSES = {"queued", "running", "staging_upload"}
MAX_UPLOAD_BYTES_DEFAULT = 500 * 1024 * 1024
SHA256_LEN = 64


class UpdatePackageError(RuntimeError):
    """Base exception containing a typed error payload for API responses."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        hint: str,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code


class UpdateValidationError(UpdatePackageError):
    """Raised when uploaded package content violates the contract."""

    def __init__(self, *, code: str, message: str, hint: str, status_code: int = 422) -> None:
        super().__init__(code=code, message=message, hint=hint, status_code=status_code)


class UpdateApplyError(UpdatePackageError):
    """Raised when a package passes validation but fails during apply."""

    def __init__(self, *, code: str, message: str, hint: str, status_code: int = 500) -> None:
        super().__init__(code=code, message=message, hint=hint, status_code=status_code)


@dataclass(frozen=True)
class ManifestComponent:
    """Typed component entry parsed from ``manifest.json``."""

    name: str
    version: str
    sha256: str
    archive_path: Optional[str] = None
    bin_path: Optional[str] = None
    flash_mode: Optional[str] = None

    @property
    def artifact_path(self) -> str:
        """Return the ZIP-internal path to the component artifact."""
        if self.archive_path:
            return self.archive_path
        if self.bin_path:
            return self.bin_path
        return ""


@dataclass(frozen=True)
class ManifestModel:
    """Validated manifest metadata and component map."""

    schema_version: str
    package_id: str
    created_at_utc: str
    created_by: str
    components: Dict[str, ManifestComponent]


@dataclass
class UpdateJob:
    """Mutable in-memory state for one update operation."""

    update_id: str
    package_filename: str
    created_at: str
    heartbeat_at: str
    status: str = "staging_upload"
    step: str = "staging_upload"
    message: str = "Receiving package upload."
    package_path: str = ""
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    manifest: Dict[str, Any] = field(default_factory=dict)
    components: Dict[str, str] = field(
        default_factory=lambda: {
            "pybeep": "skipped",
            "rest_api": "skipped",
            "firmware": "skipped",
        }
    )
    restart: Dict[str, Any] = field(default_factory=dict)
    error: Dict[str, str] = field(default_factory=dict)
    audit_log_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable snapshot."""
        return {
            "update_id": self.update_id,
            "status": self.status,
            "step": self.step,
            "message": self.message,
            "package_filename": self.package_filename,
            "package_path": self.package_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "heartbeat_at": self.heartbeat_at,
            "components": dict(self.components),
            "manifest": dict(self.manifest),
            "restart": dict(self.restart),
            "error": dict(self.error),
            "audit_log_path": self.audit_log_path,
        }


class PackageUpdateManager:
    """Orchestrate async package updates with lock-protected job state."""

    def __init__(
        self,
        *,
        repo_root: Path,
        staging_root: Path,
        audit_root: Path,
        flash_firmware: Callable[[Path], Dict[str, Any]],
        restart_service: Callable[[], Dict[str, Any]],
        max_upload_bytes: int = MAX_UPLOAD_BYTES_DEFAULT,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._staging_root = Path(staging_root)
        self._audit_root = Path(audit_root)
        self._flash_firmware = flash_firmware
        self._restart_service = restart_service
        self._max_upload_bytes = int(max_upload_bytes)
        self._log = logger or logging.getLogger("rest_api.updates")

        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._audit_root.mkdir(parents=True, exist_ok=True)

        self._jobs: Dict[str, UpdateJob] = {}
        self._job_order: list[str] = []
        self._active_update_id: Optional[str] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enqueue_upload(self, *, filename: str, source: BinaryIO) -> Dict[str, Any]:
        """Store uploaded package and start background apply worker."""
        normalized_name = self._normalize_upload_name(filename)
        update_id = uuid.uuid4().hex
        now = self._utcnow_iso()
        stage_dir = self._staging_root / update_id
        package_path = stage_dir / "update-package.zip"
        audit_path = self._audit_root / f"{update_id}.jsonl"

        with self._lock:
            if self._has_active_job_locked():
                active = self._active_update_id or "unknown"
                raise UpdateValidationError(
                    code="updates.locked",
                    message="Update already running",
                    hint=f"Wait for active update_id {active} to finish.",
                    status_code=409,
                )
            job = UpdateJob(
                update_id=update_id,
                package_filename=normalized_name,
                created_at=now,
                heartbeat_at=now,
                audit_log_path=str(audit_path),
            )
            self._jobs[update_id] = job
            self._job_order.append(update_id)
            self._active_update_id = update_id

        try:
            stage_dir.mkdir(parents=True, exist_ok=True)
            bytes_written = self._write_upload(source=source, target_path=package_path)
        except UpdatePackageError as exc:
            self._fail_job(update_id=update_id, error=exc, step="staging_upload")
            self._release_active(update_id)
            raise
        except Exception as exc:
            self._fail_job(
                update_id=update_id,
                error=UpdateApplyError(
                    code="updates.store_failed",
                    message="Failed to store uploaded package",
                    hint=str(exc) or "Check filesystem permissions and free space.",
                ),
                step="staging_upload",
            )
            self._release_active(update_id)
            raise

        with self._lock:
            job = self._jobs[update_id]
            job.package_path = str(package_path)
            job.status = "queued"
            job.step = "queued"
            job.message = "Package stored and queued for apply."
            job.heartbeat_at = self._utcnow_iso()

        self._append_audit(
            update_id,
            event="queued",
            message="Package upload received.",
            extra={"bytes_written": bytes_written, "filename": normalized_name},
        )

        worker = threading.Thread(
            target=self._run_update_job,
            args=(update_id,),
            name=f"package-update-{update_id}",
            daemon=True,
        )
        worker.start()
        return self.get_job(update_id) or {"update_id": update_id, "status": "queued"}

    def get_job(self, update_id: str) -> Optional[Dict[str, Any]]:
        """Return one update job snapshot by id."""
        key = str(update_id or "").strip()
        if not key:
            return None
        with self._lock:
            job = self._jobs.get(key)
            if not job:
                return None
            snapshot = job.to_dict()
        snapshot["observed_at"] = self._utcnow_iso()
        return snapshot

    def list_jobs(self, *, limit: int = 20) -> list[Dict[str, Any]]:
        """Return recent update jobs, newest first."""
        safe_limit = max(1, min(200, int(limit or 20)))
        with self._lock:
            ordered = list(reversed(self._job_order[-safe_limit:]))
            snapshots = [self._jobs[uid].to_dict() for uid in ordered if uid in self._jobs]
        observed_at = self._utcnow_iso()
        for snapshot in snapshots:
            snapshot["observed_at"] = observed_at
        return snapshots

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _run_update_job(self, update_id: str) -> None:
        """Background worker that validates and applies one package."""
        try:
            self._transition(
                update_id,
                status="running",
                step="validate_package",
                message="Validating manifest and checksums.",
                started=True,
            )
            manifest = self._validate_package(update_id)
            self._set_manifest(update_id, manifest)
            self._append_audit(
                update_id,
                event="validated",
                message="Package validation completed.",
                extra={"components": sorted(manifest.components.keys())},
            )

            for component_name in COMPONENT_APPLY_ORDER:
                component = manifest.components.get(component_name)
                if component is None:
                    self._set_component_state(update_id, component_name, "skipped")
                    continue

                if component_name == "pybeep":
                    self._transition(
                        update_id,
                        step="apply_pybeep",
                        message="Applying pyBEEP component.",
                    )
                    self._set_component_state(update_id, "pybeep", "running")
                    self._apply_archive_component(
                        update_id=update_id,
                        component=component,
                        target_dir=self._repo_root / "vendor" / "pyBEEP",
                        component_label="pybeep",
                    )
                    self._set_component_state(update_id, "pybeep", "done")
                    self._append_audit(
                        update_id,
                        event="component_done",
                        message="pyBEEP component applied.",
                        extra={"version": component.version},
                    )
                    continue

                if component_name == "rest_api":
                    self._transition(
                        update_id,
                        step="apply_rest_api",
                        message="Applying REST API component.",
                    )
                    self._set_component_state(update_id, "rest_api", "running")
                    self._apply_archive_component(
                        update_id=update_id,
                        component=component,
                        target_dir=self._repo_root / "rest_api",
                        component_label="rest_api",
                    )
                    self._set_component_state(update_id, "rest_api", "done")
                    self._append_audit(
                        update_id,
                        event="component_done",
                        message="REST API component applied.",
                        extra={"version": component.version},
                    )
                    continue

                if component_name == "firmware":
                    self._transition(
                        update_id,
                        step="flash_firmware",
                        message="Flashing firmware component.",
                    )
                    self._set_component_state(update_id, "firmware", "running")
                    flash_result = self._apply_firmware_component(
                        update_id=update_id,
                        component=component,
                    )
                    self._set_component_state(update_id, "firmware", "done")
                    self._append_audit(
                        update_id,
                        event="component_done",
                        message="Firmware component flashed.",
                        extra={"version": component.version, "result": flash_result},
                    )

            self._transition(
                update_id,
                step="restart_service",
                message="Restarting service.",
            )
            restart_result = dict(self._restart_service() or {})
            self._set_restart_result(update_id, restart_result)
            if not bool(restart_result.get("ok")):
                raise UpdateApplyError(
                    code="updates.restart_failed",
                    message="Service restart failed",
                    hint=str(restart_result.get("stderr") or restart_result.get("hint") or ""),
                )
            self._append_audit(
                update_id,
                event="restart_done",
                message="Service restart completed.",
                extra={"result": restart_result},
            )

            self._transition(
                update_id,
                status="done",
                step="done",
                message="Update completed successfully.",
                ended=True,
            )
            self._append_audit(
                update_id,
                event="done",
                message="Package update finished successfully.",
            )
        except UpdatePackageError as exc:
            self._fail_job(update_id=update_id, error=exc)
        except Exception as exc:
            self._fail_job(
                update_id=update_id,
                error=UpdateApplyError(
                    code="updates.unexpected_error",
                    message="Update failed with unexpected error",
                    hint=str(exc) or "Inspect server logs for details.",
                ),
            )
            self._log.exception("Unexpected package update error update_id=%s", update_id)
        finally:
            self._release_active(update_id)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_package(self, update_id: str) -> ManifestModel:
        """Validate ZIP structure, manifest schema, and checksums."""
        package_path = self._job_package_path(update_id)
        if not package_path.is_file():
            raise UpdateValidationError(
                code="updates.package_missing",
                message="Uploaded package is missing",
                hint="Upload a valid update ZIP and retry.",
                status_code=500,
            )

        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                entry_lookup = self._build_entry_lookup(archive)
                manifest_bytes = self._read_required_member(
                    archive=archive,
                    entry_lookup=entry_lookup,
                    required_path="manifest.json",
                )
                checksums_bytes = self._read_required_member(
                    archive=archive,
                    entry_lookup=entry_lookup,
                    required_path="checksums.sha256",
                )
                manifest = self._parse_manifest(manifest_bytes)
                checksums = self._parse_checksums(checksums_bytes)

                for name, component in manifest.components.items():
                    artifact_path = component.artifact_path
                    raw_entry = entry_lookup.get(artifact_path)
                    if not raw_entry:
                        raise UpdateValidationError(
                            code="updates.path_missing",
                            message="Manifest artifact path missing in ZIP",
                            hint=f"components.{name} references '{artifact_path}', but it is not present.",
                        )
                    digest = self._sha256_for_member(archive=archive, member_name=raw_entry)
                    expected_manifest = component.sha256.lower()
                    if digest != expected_manifest:
                        raise UpdateValidationError(
                            code="updates.checksum_mismatch",
                            message="Manifest checksum does not match artifact bytes",
                            hint=f"components.{name} expected sha256 {expected_manifest}, got {digest}.",
                        )
                    expected_checksums = checksums.get(artifact_path)
                    if expected_checksums is None:
                        raise UpdateValidationError(
                            code="updates.checksum_missing",
                            message="Missing checksum entry",
                            hint=f"checksums.sha256 does not include '{artifact_path}'.",
                        )
                    if digest != expected_checksums:
                        raise UpdateValidationError(
                            code="updates.checksum_mismatch",
                            message="checksums.sha256 entry does not match artifact bytes",
                            hint=f"{artifact_path} expected sha256 {expected_checksums}, got {digest}.",
                        )
                return manifest
        except zipfile.BadZipFile as exc:
            raise UpdateValidationError(
                code="updates.invalid_zip",
                message="Invalid update package",
                hint=str(exc) or "File is not a readable ZIP archive.",
            ) from exc

    def _parse_manifest(self, manifest_bytes: bytes) -> ManifestModel:
        """Decode and validate ``manifest.json`` content."""
        try:
            payload = json.loads(manifest_bytes.decode("utf-8"))
        except Exception as exc:
            raise UpdateValidationError(
                code="updates.manifest_invalid_json",
                message="manifest.json is not valid JSON",
                hint=str(exc),
            ) from exc

        if not isinstance(payload, dict):
            raise UpdateValidationError(
                code="updates.manifest_invalid",
                message="manifest.json must be a JSON object",
                hint="Use object keys schema_version/package_id/created_at_utc/created_by/components.",
            )

        schema_version = str(payload.get("schema_version") or "").strip()
        package_id = str(payload.get("package_id") or "").strip()
        created_at_utc = str(payload.get("created_at_utc") or "").strip()
        created_by = str(payload.get("created_by") or "").strip()
        components_raw = payload.get("components")

        if schema_version != "1.0":
            raise UpdateValidationError(
                code="updates.schema_unsupported",
                message="Unsupported manifest schema_version",
                hint="Use schema_version '1.0'.",
            )
        if not package_id:
            raise UpdateValidationError(
                code="updates.manifest_missing_field",
                message="manifest.json missing package_id",
                hint="Provide a non-empty package_id.",
            )
        if not created_at_utc:
            raise UpdateValidationError(
                code="updates.manifest_missing_field",
                message="manifest.json missing created_at_utc",
                hint="Provide ISO UTC timestamp for created_at_utc.",
            )
        if not created_by:
            raise UpdateValidationError(
                code="updates.manifest_missing_field",
                message="manifest.json missing created_by",
                hint="Provide author/tool identifier for created_by.",
            )
        if not isinstance(components_raw, dict) or not components_raw:
            raise UpdateValidationError(
                code="updates.manifest_missing_components",
                message="manifest.json components must be a non-empty object",
                hint="Include at least one component entry (rest_api, pybeep, or firmware).",
            )

        components: Dict[str, ManifestComponent] = {}
        for name, value in components_raw.items():
            key = str(name or "").strip()
            if key not in SUPPORTED_COMPONENTS:
                raise UpdateValidationError(
                    code="updates.component_unknown",
                    message="Unsupported component in manifest",
                    hint=f"Allowed components: {', '.join(SUPPORTED_COMPONENTS)}.",
                )
            if not isinstance(value, dict):
                raise UpdateValidationError(
                    code="updates.component_invalid",
                    message=f"components.{key} must be an object",
                    hint="Provide version/path/sha256 fields.",
                )

            version = str(value.get("version") or "").strip()
            sha256 = self._normalize_sha(
                value.get("sha256"),
                field=f"components.{key}.sha256",
            )
            if not version:
                raise UpdateValidationError(
                    code="updates.component_invalid",
                    message=f"components.{key}.version must be non-empty",
                    hint="Provide a component version string.",
                )

            archive_path: Optional[str] = None
            bin_path: Optional[str] = None
            flash_mode: Optional[str] = None
            if key in {"pybeep", "rest_api"}:
                archive_path = self._normalize_zip_path(
                    value.get("archive_path"),
                    field=f"components.{key}.archive_path",
                )
            else:
                bin_path = self._normalize_zip_path(
                    value.get("bin_path"),
                    field=f"components.{key}.bin_path",
                )
                if not bin_path.lower().endswith(".bin"):
                    raise UpdateValidationError(
                        code="updates.component_invalid",
                        message=f"components.{key}.bin_path must point to a .bin file",
                        hint="Use firmware/<name>.bin for firmware component path.",
                    )
                flash_mode_raw = value.get("flash_mode")
                if flash_mode_raw is not None:
                    flash_mode = str(flash_mode_raw).strip()
                    if flash_mode != "reuse_firmware_endpoint_logic":
                        raise UpdateValidationError(
                            code="updates.component_invalid",
                            message="Unsupported firmware flash_mode",
                            hint="Use flash_mode 'reuse_firmware_endpoint_logic' or omit the field.",
                        )

            components[key] = ManifestComponent(
                name=key,
                version=version,
                sha256=sha256,
                archive_path=archive_path,
                bin_path=bin_path,
                flash_mode=flash_mode,
            )

        return ManifestModel(
            schema_version=schema_version,
            package_id=package_id,
            created_at_utc=created_at_utc,
            created_by=created_by,
            components=components,
        )

    def _parse_checksums(self, checksums_bytes: bytes) -> Dict[str, str]:
        """Decode and validate `checksums.sha256` entries."""
        try:
            text = checksums_bytes.decode("utf-8")
        except Exception as exc:
            raise UpdateValidationError(
                code="updates.checksum_invalid",
                message="checksums.sha256 is not valid UTF-8 text",
                hint=str(exc),
            ) from exc

        entries: Dict[str, str] = {}
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            parts = raw.split(maxsplit=1)
            if len(parts) != 2:
                raise UpdateValidationError(
                    code="updates.checksum_invalid",
                    message="Malformed checksums.sha256 line",
                    hint=f"Expected '<sha256> <path>', got '{raw}'.",
                )
            digest = self._normalize_sha(parts[0], field="checksums.sha256 digest")
            path_token = parts[1].strip()
            if path_token.startswith("*"):
                path_token = path_token[1:]
            canonical_path = self._normalize_zip_path(
                path_token,
                field="checksums.sha256 path",
            )
            entries[canonical_path] = digest

        if not entries:
            raise UpdateValidationError(
                code="updates.checksum_missing",
                message="checksums.sha256 is empty",
                hint="Provide checksum lines for every component artifact.",
            )
        return entries

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _apply_archive_component(
        self,
        *,
        update_id: str,
        component: ManifestComponent,
        target_dir: Path,
        component_label: str,
    ) -> None:
        """Extract and sync one TAR component archive into target directory."""
        stage_dir = self._staging_root / update_id / component_label
        archive_path = stage_dir / "bundle.tar.gz"
        extract_dir = stage_dir / "extract"
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        package_path = self._job_package_path(update_id)
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                entry_lookup = self._build_entry_lookup(archive)
                entry_name = entry_lookup.get(component.artifact_path)
                if not entry_name:
                    raise UpdateApplyError(
                        code="updates.apply_missing_component",
                        message="Component artifact missing during apply",
                        hint=f"{component_label} artifact '{component.artifact_path}' not found in package.",
                    )
                with archive.open(entry_name, "r") as source, archive_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
        except UpdatePackageError:
            raise
        except Exception as exc:
            raise UpdateApplyError(
                code="updates.apply_extract_failed",
                message=f"Failed to stage {component_label} archive",
                hint=str(exc),
            ) from exc

        self._safe_extract_tar(archive_path=archive_path, target_dir=extract_dir)
        source_root = self._resolve_extract_root(extract_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        self._sync_tree(source_root=source_root, target_dir=target_dir)

    def _apply_firmware_component(
        self,
        *,
        update_id: str,
        component: ManifestComponent,
    ) -> Dict[str, Any]:
        """Extract firmware binary and execute shared flash callback."""
        stage_dir = self._staging_root / update_id / "firmware"
        firmware_path = stage_dir / Path(component.artifact_path).name
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        package_path = self._job_package_path(update_id)
        try:
            with zipfile.ZipFile(package_path, "r") as archive:
                entry_lookup = self._build_entry_lookup(archive)
                entry_name = entry_lookup.get(component.artifact_path)
                if not entry_name:
                    raise UpdateApplyError(
                        code="updates.apply_missing_component",
                        message="Firmware artifact missing during apply",
                        hint=f"Firmware path '{component.artifact_path}' is missing in package.",
                    )
                with archive.open(entry_name, "r") as source, firmware_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
        except UpdatePackageError:
            raise
        except Exception as exc:
            raise UpdateApplyError(
                code="updates.apply_extract_failed",
                message="Failed to stage firmware binary",
                hint=str(exc),
            ) from exc

        try:
            result = dict(self._flash_firmware(firmware_path) or {})
        except UpdatePackageError:
            raise
        except Exception as exc:
            raise UpdateApplyError(
                code="updates.flash_failed",
                message="Firmware flashing failed",
                hint=str(exc),
            ) from exc

        if not bool(result.get("ok", True)):
            raise UpdateApplyError(
                code="updates.flash_failed",
                message="Firmware flashing failed",
                hint=str(result.get("hint") or result.get("stderr") or ""),
            )
        return result

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------
    def _transition(
        self,
        update_id: str,
        *,
        status: Optional[str] = None,
        step: Optional[str] = None,
        message: Optional[str] = None,
        started: bool = False,
        ended: bool = False,
    ) -> None:
        """Update mutable job state safely."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            if status is not None:
                job.status = status
            if step is not None:
                job.step = step
            if message is not None:
                job.message = message
            if started and not job.started_at:
                job.started_at = self._utcnow_iso()
            if ended:
                job.ended_at = self._utcnow_iso()
            job.heartbeat_at = self._utcnow_iso()

    def _set_manifest(self, update_id: str, manifest: ManifestModel) -> None:
        """Persist parsed manifest metadata into job snapshot."""
        manifest_payload = {
            "schema_version": manifest.schema_version,
            "package_id": manifest.package_id,
            "created_at_utc": manifest.created_at_utc,
            "created_by": manifest.created_by,
            "components": {
                name: {
                    "version": component.version,
                    "sha256": component.sha256,
                    "archive_path": component.archive_path,
                    "bin_path": component.bin_path,
                    "flash_mode": component.flash_mode,
                }
                for name, component in manifest.components.items()
            },
        }
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            job.manifest = manifest_payload
            job.heartbeat_at = self._utcnow_iso()

    def _set_component_state(self, update_id: str, component: str, state: str) -> None:
        """Update one component apply status."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            job.components[str(component)] = str(state)
            job.heartbeat_at = self._utcnow_iso()

    def _set_restart_result(self, update_id: str, result: Dict[str, Any]) -> None:
        """Attach restart command result to job status."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            job.restart = dict(result or {})
            job.heartbeat_at = self._utcnow_iso()

    def _fail_job(
        self,
        *,
        update_id: str,
        error: UpdatePackageError,
        step: Optional[str] = None,
    ) -> None:
        """Mark a job as failed and append audit context."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            job.status = "failed"
            if step:
                job.step = step
            job.message = error.message
            job.error = {"code": error.code, "message": error.message, "hint": error.hint}
            if not job.started_at:
                job.started_at = self._utcnow_iso()
            job.ended_at = self._utcnow_iso()
            job.heartbeat_at = self._utcnow_iso()
        self._append_audit(
            update_id,
            event="failed",
            message=error.message,
            extra={"code": error.code, "hint": error.hint},
        )

    def _release_active(self, update_id: str) -> None:
        """Release global update lock when the owning job is finished."""
        with self._lock:
            if self._active_update_id == update_id:
                self._active_update_id = None

    def _has_active_job_locked(self) -> bool:
        """Return whether a running or queued job currently holds the lock."""
        if not self._active_update_id:
            return False
        active_job = self._jobs.get(self._active_update_id)
        if active_job is None:
            self._active_update_id = None
            return False
        if active_job.status in TERMINAL_STATUSES:
            self._active_update_id = None
            return False
        return active_job.status in RUNNING_STATUSES

    def _job_package_path(self, update_id: str) -> Path:
        """Resolve staged ZIP path for one job."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return Path("")
            return Path(job.package_path)

    def _append_audit(
        self,
        update_id: str,
        *,
        event: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one JSONL audit event."""
        with self._lock:
            job = self._jobs.get(update_id)
            if not job:
                return
            audit_path = Path(job.audit_log_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": self._utcnow_iso(),
            "update_id": update_id,
            "event": event,
            "message": message,
        }
        if extra:
            payload["extra"] = extra
        try:
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
                handle.write("\n")
        except Exception:
            self._log.exception("Failed writing update audit entry update_id=%s", update_id)

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------
    def _normalize_upload_name(self, filename: str) -> str:
        """Validate upload filename and enforce ZIP extension."""
        normalized = Path(str(filename or "")).name.strip()
        if not normalized:
            raise UpdateValidationError(
                code="updates.invalid_upload",
                message="Invalid update upload",
                hint="Upload a .zip package file.",
                status_code=400,
            )
        if not normalized.lower().endswith(".zip"):
            raise UpdateValidationError(
                code="updates.invalid_upload",
                message="Invalid update upload",
                hint="Only .zip files are allowed.",
                status_code=400,
            )
        return normalized

    def _write_upload(self, *, source: BinaryIO, target_path: Path) -> int:
        """Copy uploaded file stream to disk with size enforcement."""
        bytes_written = 0
        chunk_size = 1024 * 1024
        try:
            with target_path.open("wb") as handle:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > self._max_upload_bytes:
                        raise UpdateValidationError(
                            code="updates.upload_too_large",
                            message="Update package exceeds size limit",
                            hint=f"Maximum package size is {self._max_upload_bytes} bytes.",
                            status_code=413,
                        )
                    handle.write(chunk)
        except UpdatePackageError:
            raise
        except Exception as exc:
            raise UpdateApplyError(
                code="updates.store_failed",
                message="Failed to store uploaded package",
                hint=str(exc),
            ) from exc
        if bytes_written <= 0:
            raise UpdateValidationError(
                code="updates.invalid_upload",
                message="Uploaded package is empty",
                hint="Upload a non-empty update ZIP file.",
                status_code=400,
            )
        return bytes_written

    def _build_entry_lookup(self, archive: zipfile.ZipFile) -> Dict[str, str]:
        """Build canonical path map for ZIP members."""
        lookup: Dict[str, str] = {}
        for name in archive.namelist():
            if not name or name.endswith("/"):
                continue
            canonical = self._normalize_zip_path(name, field="zip member")
            if canonical in lookup and lookup[canonical] != name:
                raise UpdateValidationError(
                    code="updates.invalid_zip",
                    message="ZIP contains duplicate canonical paths",
                    hint=f"Duplicate path detected: {canonical}.",
                )
            lookup[canonical] = name
        return lookup

    def _read_required_member(
        self,
        *,
        archive: zipfile.ZipFile,
        entry_lookup: Dict[str, str],
        required_path: str,
    ) -> bytes:
        """Read one required ZIP member by canonical path."""
        member_name = entry_lookup.get(required_path)
        if not member_name:
            raise UpdateValidationError(
                code="updates.path_missing",
                message=f"Missing required file: {required_path}",
                hint=f"Add '{required_path}' to the ZIP root.",
            )
        try:
            return archive.read(member_name)
        except Exception as exc:
            raise UpdateValidationError(
                code="updates.invalid_zip",
                message=f"Could not read required file: {required_path}",
                hint=str(exc),
            ) from exc

    def _sha256_for_member(self, *, archive: zipfile.ZipFile, member_name: str) -> str:
        """Compute SHA-256 digest for one ZIP member."""
        digest = hashlib.sha256()
        with archive.open(member_name, "r") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest().lower()

    def _safe_extract_tar(self, *, archive_path: Path, target_dir: Path) -> None:
        """Extract TAR archive with traversal/link safety checks."""
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive_path, "r:*") as tar:
                members = tar.getmembers()
                for member in members:
                    member_path = PurePosixPath(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise UpdateApplyError(
                            code="updates.unsafe_archive_path",
                            message="Archive contains unsafe path",
                            hint=f"Unsafe member path: {member.name}",
                        )
                    if member.issym() or member.islnk():
                        raise UpdateApplyError(
                            code="updates.unsafe_archive_path",
                            message="Archive contains link entries",
                            hint=f"Unsupported link member: {member.name}",
                        )
                tar.extractall(path=target_dir)
        except UpdatePackageError:
            raise
        except Exception as exc:
            raise UpdateApplyError(
                code="updates.apply_extract_failed",
                message="Failed to extract component archive",
                hint=str(exc),
            ) from exc

    def _resolve_extract_root(self, extract_dir: Path) -> Path:
        """Resolve extraction root to avoid double-nested component folders."""
        entries = [path for path in extract_dir.iterdir()]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extract_dir

    def _sync_tree(self, *, source_root: Path, target_dir: Path) -> None:
        """Merge extracted component files into target directory."""
        for item in source_root.iterdir():
            destination = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)

    def _normalize_zip_path(self, value: Any, *, field: str) -> str:
        """Canonicalize ZIP-internal relative paths and reject unsafe values."""
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            raise UpdateValidationError(
                code="updates.path_invalid",
                message=f"Invalid {field}",
                hint=f"{field} must be a non-empty relative ZIP path.",
            )
        pure = PurePosixPath(text)
        if pure.is_absolute():
            raise UpdateValidationError(
                code="updates.path_invalid",
                message=f"Invalid {field}",
                hint=f"{field} must be relative, not absolute.",
            )
        parts = pure.parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise UpdateValidationError(
                code="updates.path_invalid",
                message=f"Invalid {field}",
                hint=f"{field} must not contain '.', '..', or empty path segments.",
            )
        return pure.as_posix()

    def _normalize_sha(self, value: Any, *, field: str) -> str:
        """Validate SHA-256 text format."""
        digest = str(value or "").strip().lower()
        if len(digest) != SHA256_LEN or any(ch not in "0123456789abcdef" for ch in digest):
            raise UpdateValidationError(
                code="updates.checksum_invalid",
                message=f"Invalid {field}",
                hint=f"{field} must be a 64-character lowercase hex SHA-256 value.",
            )
        return digest

    @staticmethod
    def _utcnow_iso() -> str:
        """Return ISO UTC timestamp used across job payloads and audits."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_terminal_update_status(status: str) -> bool:
    """Return whether update status denotes terminal completion."""
    normalized = str(status or "").strip().lower()
    return normalized in TERMINAL_STATUSES


def iter_running_statuses(jobs: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    """Yield jobs that are still active (queued/running/staging)."""
    for job in jobs:
        status = str((job or {}).get("status") or "").strip().lower()
        if status in RUNNING_STATUSES:
            yield job
