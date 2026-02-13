"""Remote update archive validation and application service.

This module encapsulates the remote update workflow used by ``rest_api.app``.
It owns:

- upload persistence,
- secure ZIP extraction,
- strict manifest validation,
- checksum verification,
- atomic directory replacement with backups, and
- in-memory update job status snapshots for polling endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import threading
from typing import BinaryIO, Dict, List, Mapping, Optional
import uuid
import zipfile


ALLOWED_COMPONENTS: tuple[str, ...] = ("rest_api", "pybeep_vendor", "firmware_bundle")
STEP_VALIDATE_ARCHIVE = "validate_archive"
STEP_APPLY_REST_API = "apply_rest_api"
STEP_APPLY_PYBEEP = "apply_pybeep_vendor"
STEP_STAGE_FIRMWARE = "stage_firmware"
STEP_ORDER: tuple[str, ...] = (
    STEP_VALIDATE_ARCHIVE,
    STEP_APPLY_REST_API,
    STEP_APPLY_PYBEEP,
    STEP_STAGE_FIRMWARE,
)
PYBEEP_TARGET_PLACEHOLDER = "<REPOSITORY_PATH>/vendor/pyBEEP"


def _utc_now_iso() -> str:
    """Return timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class UpdateServiceError(RuntimeError):
    """Typed update service error with stable API code/message/hint values."""

    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.hint = str(hint or "")


@dataclass
class UpdateStepState:
    """Mutable state for one update pipeline step."""

    step: str
    status: str = "pending"
    message: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Return wire-format dictionary used by FastAPI responses."""
        payload = {"step": self.step, "status": self.status}
        if self.message:
            payload["message"] = self.message
        return payload


@dataclass
class UpdateComponentResult:
    """Mutable state for one component result in a completed/partial job."""

    component: str
    action: str
    from_version: str = "unknown"
    to_version: str = "unknown"
    message: str = ""
    error_code: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Return wire-format dictionary used by FastAPI responses."""
        payload = {
            "component": self.component,
            "action": self.action,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "message": self.message,
        }
        if self.error_code:
            payload["error_code"] = self.error_code
        return payload


@dataclass
class UpdateJobState:
    """Mutable status state for one update id."""

    update_id: str
    status: str = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    bundle_version: str = ""
    steps: Dict[str, UpdateStepState] = field(default_factory=dict)
    component_results: List[UpdateComponentResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        """Serialize job state into endpoint payload shape."""
        return {
            "update_id": self.update_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "bundle_version": self.bundle_version,
            "steps": [self.steps[step].to_dict() for step in STEP_ORDER],
            "component_results": [item.to_dict() for item in self.component_results],
        }


@dataclass(frozen=True)
class _ManifestComponent:
    """Validated manifest component record."""

    present: bool
    source_dir: Optional[str] = None
    source_file: Optional[str] = None
    sha256: Optional[str] = None
    version: str = "unknown"


@dataclass(frozen=True)
class _ManifestPayload:
    """Validated manifest payload consumed by apply logic."""

    bundle_version: str
    api_target_env_var: str
    components: Dict[str, _ManifestComponent]


def compute_file_sha256(path: Path) -> str:
    """Compute SHA256 hash for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def compute_directory_sha256(path: Path) -> str:
    """Compute deterministic SHA256 for a directory tree."""
    digest = hashlib.sha256()
    files: List[Path] = [entry for entry in path.rglob("*") if entry.is_file()]
    for entry in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
        rel_path = entry.relative_to(path).as_posix().encode("utf-8")
        digest.update(rel_path)
        digest.update(b"\0")
        with entry.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


class UpdateService:
    """Apply strict ZIP update bundles and expose pollable job state."""

    def __init__(
        self,
        *,
        updates_root: Path,
        firmware_dir: Path,
        repository_root: Path,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.log = logger or logging.getLogger("rest_api.update_service")
        self.updates_root = Path(updates_root)
        self.firmware_dir = Path(firmware_dir)
        self.repository_root = Path(repository_root)
        self.incoming_root = self.updates_root / "incoming"
        self.staging_root = self.updates_root / "staging"
        self.backups_root = self.updates_root / "backups"
        self.staged_metadata_path = self.firmware_dir / "staged_firmware.json"
        self.pybeep_target_dir = self.repository_root / "vendor" / "pyBEEP"

        for directory in (self.incoming_root, self.staging_root, self.backups_root, self.firmware_dir):
            directory.mkdir(parents=True, exist_ok=True)

        self._jobs: Dict[str, UpdateJobState] = {}
        self._latest_update_id: Optional[str] = None
        self._lock = threading.Lock()

    def start_update(self, upload_name: str, upload_stream: BinaryIO) -> Dict[str, object]:
        """Persist an uploaded archive and start async processing."""
        original_name = Path(str(upload_name or "")).name
        if not original_name:
            raise UpdateServiceError(
                "update.invalid_upload",
                "Invalid update upload",
                "Upload a .zip remote update bundle.",
            )
        if not original_name.lower().endswith(".zip"):
            raise UpdateServiceError(
                "update.invalid_upload",
                "Invalid update upload",
                "Only .zip files are allowed.",
            )

        update_id = uuid.uuid4().hex
        archive_path = self.incoming_root / f"{update_id}.zip"
        try:
            with archive_path.open("wb") as handle:
                shutil.copyfileobj(upload_stream, handle)
        except Exception as exc:  # pragma: no cover - storage failure path
            raise UpdateServiceError(
                "update.invalid_upload",
                "Invalid update upload",
                f"Failed to store uploaded ZIP: {exc}",
            ) from exc

        # Perform strict contract validation before enqueueing a long-running job
        # so malformed bundles fail fast with 4xx responses.
        try:
            manifest = self._preflight_validate_archive(update_id, archive_path)
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise

        job = UpdateJobState(
            update_id=update_id,
            status="queued",
            bundle_version=manifest.bundle_version,
            steps={step: UpdateStepState(step=step, status="pending") for step in STEP_ORDER},
        )
        with self._lock:
            self._jobs[update_id] = job
            self._latest_update_id = update_id

        worker = threading.Thread(
            target=self._run_update_job,
            args=(update_id, archive_path),
            name=f"remote-update-{update_id}",
            daemon=True,
        )
        worker.start()
        return {"update_id": update_id, "status": "queued"}

    def get_status(self, update_id: str) -> Optional[Dict[str, object]]:
        """Return serialized update status for one update id."""
        with self._lock:
            job = self._jobs.get(str(update_id))
            if job is None:
                return None
            return job.to_dict()

    def get_latest_status(self) -> Optional[Dict[str, object]]:
        """Return serialized update status for the most recent update id."""
        with self._lock:
            latest = self._latest_update_id
        if not latest:
            return None
        return self.get_status(latest)

    def get_staged_firmware_info(self) -> Dict[str, str]:
        """Return staged firmware metadata for `/version` and flash endpoints."""
        if not self.staged_metadata_path.is_file():
            return {}
        try:
            payload = json.loads(self.staged_metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, Mapping):
            return {}
        return {
            "version": str(payload.get("version") or "unknown"),
            "file_name": str(payload.get("file_name") or ""),
            "sha256": str(payload.get("sha256") or ""),
            "update_id": str(payload.get("update_id") or ""),
            "staged_at": str(payload.get("staged_at") or ""),
        }

    def _preflight_validate_archive(self, update_id: str, archive_path: Path) -> _ManifestPayload:
        """Run strict archive validation before queueing a background apply job."""
        staging_dir = self.staging_root / f".preflight-{update_id}"
        try:
            self._reset_directory(staging_dir)
            self._secure_extract_archive(archive_path, staging_dir)
            manifest = self._load_manifest(staging_dir)
            self._validate_manifest_paths(manifest)
            self._validate_manifest_checksums(manifest, staging_dir)
            return manifest
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def _run_update_job(self, update_id: str, archive_path: Path) -> None:
        """Execute validation and apply pipeline for one update archive."""
        started_at = _utc_now_iso()
        self._set_job_fields(update_id, status="running", started_at=started_at)
        self._set_step(update_id, STEP_VALIDATE_ARCHIVE, "running")

        staging_dir = self.staging_root / update_id
        backup_dir = self.backups_root / f"{started_at.replace(':', '').replace('.', '')}_{update_id}"

        try:
            self._reset_directory(staging_dir)
            self._secure_extract_archive(archive_path, staging_dir)
            manifest = self._load_manifest(staging_dir)
            self._set_job_fields(update_id, bundle_version=manifest.bundle_version)
            self._validate_manifest_paths(manifest)
            self._validate_manifest_checksums(manifest, staging_dir)
            self._set_step(update_id, STEP_VALIDATE_ARCHIVE, "done")
            self._apply_components(update_id, manifest, staging_dir, backup_dir)
        except UpdateServiceError as exc:
            self.log.warning("Update %s failed: %s (%s)", update_id, exc.message, exc.code)
            self._set_step_on_failure(update_id, exc)
            self._finish_job(update_id)
            return
        except Exception as exc:  # pragma: no cover - defensive guard
            self.log.exception("Unexpected update failure update_id=%s", update_id)
            wrapped = UpdateServiceError(
                "update.manifest_invalid",
                "Update job failed unexpectedly",
                str(exc),
            )
            self._set_step_on_failure(update_id, wrapped)
            self._finish_job(update_id)
            return
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        self._finish_job(update_id)

    def _apply_components(
        self,
        update_id: str,
        manifest: _ManifestPayload,
        staging_dir: Path,
        backup_dir: Path,
    ) -> None:
        """Apply each component in deterministic order."""
        rest_component = manifest.components["rest_api"]
        self._apply_directory_component(
            update_id=update_id,
            step_name=STEP_APPLY_REST_API,
            component_name="rest_api",
            component=rest_component,
            staging_dir=staging_dir,
            backup_dir=backup_dir,
            target_dir=self._resolve_api_target_dir(manifest.api_target_env_var),
            failure_code="update.apply_rest_api_failed",
        )

        pybeep_component = manifest.components["pybeep_vendor"]
        self._apply_directory_component(
            update_id=update_id,
            step_name=STEP_APPLY_PYBEEP,
            component_name="pybeep_vendor",
            component=pybeep_component,
            staging_dir=staging_dir,
            backup_dir=backup_dir,
            target_dir=self.pybeep_target_dir,
            failure_code="update.apply_pybeep_failed",
        )

        firmware_component = manifest.components["firmware_bundle"]
        self._apply_firmware_component(update_id, firmware_component, staging_dir)

    def _apply_directory_component(
        self,
        *,
        update_id: str,
        step_name: str,
        component_name: str,
        component: _ManifestComponent,
        staging_dir: Path,
        backup_dir: Path,
        target_dir: Path,
        failure_code: str,
    ) -> None:
        """Apply one directory component with backup and atomic swap."""
        if not component.present:
            self._set_step(update_id, step_name, "skipped", "Component not present in bundle.")
            self._append_component_result(
                update_id,
                UpdateComponentResult(
                    component=component_name,
                    action="skipped",
                    to_version=component.version,
                    message="Component not present in bundle.",
                ),
            )
            return

        source_dir = staging_dir / str(component.source_dir or "")
        if not source_dir.is_dir():
            raise UpdateServiceError(
                "update.manifest_invalid",
                f"Manifest source directory missing: {source_dir}",
                f"Component '{component_name}' requires an existing source_dir.",
            )

        self._set_step(update_id, step_name, "running")
        try:
            self._replace_directory_atomically(
                source_dir=source_dir,
                target_dir=target_dir,
                backup_dir=backup_dir / component_name,
            )
        except UpdateServiceError:
            raise
        except Exception as exc:
            raise UpdateServiceError(
                failure_code,
                f"Failed to apply {component_name}",
                str(exc),
            ) from exc

        self._set_step(update_id, step_name, "done")
        self._append_component_result(
            update_id,
            UpdateComponentResult(
                component=component_name,
                action="updated",
                to_version=component.version,
                message=f"Updated files in {target_dir}.",
            ),
        )

    def _apply_firmware_component(
        self,
        update_id: str,
        component: _ManifestComponent,
        staging_dir: Path,
    ) -> None:
        """Stage firmware bundle file without flashing."""
        if not component.present:
            self._set_step(update_id, STEP_STAGE_FIRMWARE, "skipped", "Component not present in bundle.")
            self._append_component_result(
                update_id,
                UpdateComponentResult(
                    component="firmware_bundle",
                    action="skipped",
                    to_version=component.version,
                    message="Component not present in bundle.",
                ),
            )
            return

        source_file = staging_dir / str(component.source_file or "")
        if not source_file.is_file():
            raise UpdateServiceError(
                "update.manifest_invalid",
                f"Manifest firmware source file missing: {source_file}",
                "firmware_bundle.present=true requires source_file.",
            )
        if source_file.suffix.lower() != ".bin":
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Firmware bundle source must be a .bin file",
                f"Got '{source_file.name}'.",
            )

        self._set_step(update_id, STEP_STAGE_FIRMWARE, "running")
        previous = self.get_staged_firmware_info()
        try:
            target_name = source_file.name
            target_path = self.firmware_dir / target_name
            shutil.copy2(source_file, target_path)
            metadata = {
                "version": component.version,
                "file_name": target_name,
                "sha256": component.sha256 or "",
                "update_id": update_id,
                "staged_at": _utc_now_iso(),
            }
            self.staged_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        except Exception as exc:
            raise UpdateServiceError(
                "update.stage_firmware_failed",
                "Failed to stage firmware bundle",
                str(exc),
            ) from exc

        self._set_step(update_id, STEP_STAGE_FIRMWARE, "done")
        self._append_component_result(
            update_id,
            UpdateComponentResult(
                component="firmware_bundle",
                action="staged",
                from_version=previous.get("version") or "unknown",
                to_version=component.version,
                message=f"Firmware staged at {self.firmware_dir / source_file.name}.",
            ),
        )

    def _load_manifest(self, staging_dir: Path) -> _ManifestPayload:
        """Load and validate manifest JSON from extracted archive."""
        manifest_path = staging_dir / "manifest.json"
        if not manifest_path.is_file():
            raise UpdateServiceError(
                "update.manifest_missing",
                "manifest.json is missing from update bundle",
                "Add manifest.json at ZIP root.",
            )
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "manifest.json is invalid JSON",
                str(exc),
            ) from exc
        return self._validate_manifest_payload(payload)

    def _validate_manifest_payload(self, payload: object) -> _ManifestPayload:
        """Validate manifest schema and normalize to dataclass payload."""
        if not isinstance(payload, Mapping):
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest must be a JSON object",
                "manifest.json root must be an object.",
            )

        manifest_version = payload.get("manifest_version")
        if manifest_version != 1:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Unsupported manifest_version",
                "This installer expects manifest_version=1.",
            )

        bundle_version = str(payload.get("bundle_version") or "").strip()
        if not bundle_version:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest bundle_version is required",
                "Provide a non-empty bundle_version string.",
            )

        raw_paths = payload.get("paths")
        if not isinstance(raw_paths, Mapping):
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest paths object is required",
                "Provide paths.api_target_env_var and paths.pybeep_target.",
            )
        api_target_env_var = str(raw_paths.get("api_target_env_var") or "").strip()
        if not api_target_env_var:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest paths.api_target_env_var is required",
                "Set the environment variable name used for REST API target directory.",
            )
        pybeep_target = str(raw_paths.get("pybeep_target") or "").strip()
        if pybeep_target != PYBEEP_TARGET_PLACEHOLDER:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest paths.pybeep_target is invalid",
                f"Expected '{PYBEEP_TARGET_PLACEHOLDER}'.",
            )

        components_payload = payload.get("components")
        if not isinstance(components_payload, Mapping):
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest components object is required",
                "Provide rest_api, pybeep_vendor, and firmware_bundle keys.",
            )

        unknown = sorted(set(components_payload.keys()) - set(ALLOWED_COMPONENTS))
        if unknown:
            raise UpdateServiceError(
                "update.manifest_unknown_component",
                "Manifest contains unknown components",
                ", ".join(unknown),
            )

        missing = [name for name in ALLOWED_COMPONENTS if name not in components_payload]
        if missing:
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Manifest is missing required component keys",
                ", ".join(missing),
            )

        components: Dict[str, _ManifestComponent] = {}
        for component_name in ALLOWED_COMPONENTS:
            component_payload = components_payload.get(component_name)
            if not isinstance(component_payload, Mapping):
                raise UpdateServiceError(
                    "update.manifest_invalid",
                    f"Manifest component '{component_name}' must be an object",
                    "Check component JSON shape.",
                )

            present = bool(component_payload.get("present"))
            sha256 = str(component_payload.get("sha256") or "").strip().lower() or None
            version = str(component_payload.get("version") or "unknown").strip() or "unknown"
            source_dir = component_payload.get("source_dir")
            source_file = component_payload.get("source_file")

            if present and not sha256:
                raise UpdateServiceError(
                    "update.manifest_invalid",
                    f"Component '{component_name}' is missing sha256",
                    "Each present component requires a SHA256 checksum.",
                )

            if component_name in ("rest_api", "pybeep_vendor"):
                if present and not source_dir:
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        f"Component '{component_name}' requires source_dir",
                        "Set source_dir when present=true.",
                    )
                if source_file:
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        f"Component '{component_name}' cannot define source_file",
                        "Use source_dir for directory components.",
                    )
            if component_name == "firmware_bundle":
                if present and not source_file:
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        "Component 'firmware_bundle' requires source_file",
                        "Set source_file when present=true.",
                    )
                if source_dir:
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        "Component 'firmware_bundle' cannot define source_dir",
                        "Use source_file for firmware_bundle.",
                    )

            components[component_name] = _ManifestComponent(
                present=present,
                source_dir=str(source_dir).strip() if source_dir else None,
                source_file=str(source_file).strip() if source_file else None,
                sha256=sha256,
                version=version,
            )

        return _ManifestPayload(
            bundle_version=bundle_version,
            api_target_env_var=api_target_env_var,
            components=components,
        )

    def _validate_manifest_paths(self, manifest: _ManifestPayload) -> None:
        """Validate environment-backed target directory contract."""
        _ = self._resolve_api_target_dir(manifest.api_target_env_var)
        self.pybeep_target_dir.parent.mkdir(parents=True, exist_ok=True)

    def _validate_manifest_checksums(self, manifest: _ManifestPayload, staging_dir: Path) -> None:
        """Validate checksums for each present component."""
        for component_name, component in manifest.components.items():
            if not component.present:
                continue
            expected = str(component.sha256 or "").strip().lower()
            if component_name in ("rest_api", "pybeep_vendor"):
                source_path = staging_dir / str(component.source_dir or "")
                if not source_path.is_dir():
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        f"Manifest source directory missing: {source_path}",
                        f"Component '{component_name}' requires an existing directory.",
                    )
                actual = compute_directory_sha256(source_path).lower()
            else:
                source_path = staging_dir / str(component.source_file or "")
                if not source_path.is_file():
                    raise UpdateServiceError(
                        "update.manifest_invalid",
                        f"Manifest source file missing: {source_path}",
                        "firmware_bundle present=true requires an existing source_file.",
                    )
                actual = compute_file_sha256(source_path).lower()

            if actual != expected:
                raise UpdateServiceError(
                    "update.checksum_mismatch",
                    f"Checksum mismatch for component '{component_name}'",
                    f"expected={expected} actual={actual}",
                )

    def _resolve_api_target_dir(self, env_var_name: str) -> Path:
        """Resolve API target directory using manifest-defined env var name."""
        raw = os.getenv(env_var_name, "").strip()
        if not raw:
            raise UpdateServiceError(
                "update.apply_rest_api_failed",
                "REST API target directory is not configured",
                f"Set environment variable '{env_var_name}'.",
            )
        return Path(raw).expanduser().resolve()

    @staticmethod
    def _reset_directory(path: Path) -> None:
        """Delete and recreate a directory path."""
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)

    def _secure_extract_archive(self, archive_path: Path, destination: Path) -> None:
        """Extract ZIP safely and prevent path traversal or symlink escapes."""
        destination_root = destination.resolve()
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                for entry in archive.infolist():
                    name = entry.filename.replace("\\", "/")
                    if not name:
                        continue
                    pure = PurePosixPath(name)
                    if pure.is_absolute() or any(part in ("", "..") for part in pure.parts):
                        raise UpdateServiceError(
                            "update.manifest_invalid",
                            "Unsafe ZIP entry path detected",
                            name,
                        )
                    mode = (entry.external_attr >> 16) & 0o170000
                    if mode == 0o120000:
                        raise UpdateServiceError(
                            "update.manifest_invalid",
                            "ZIP archive contains symlink entry",
                            name,
                        )
                    target_path = destination / pure.as_posix()
                    resolved_target = target_path.resolve()
                    if destination_root not in (resolved_target, *resolved_target.parents):
                        raise UpdateServiceError(
                            "update.manifest_invalid",
                            "ZIP entry escaped extraction directory",
                            name,
                        )
                    if entry.is_dir():
                        resolved_target.mkdir(parents=True, exist_ok=True)
                        continue
                    resolved_target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry, "r") as source, resolved_target.open("wb") as handle:
                        shutil.copyfileobj(source, handle)
        except UpdateServiceError:
            raise
        except zipfile.BadZipFile as exc:
            raise UpdateServiceError(
                "update.invalid_upload",
                "Invalid update upload",
                f"Could not open ZIP archive: {exc}",
            ) from exc

    def _replace_directory_atomically(self, *, source_dir: Path, target_dir: Path, backup_dir: Path) -> None:
        """Replace target directory with source data using atomic renames."""
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        work_id = uuid.uuid4().hex
        incoming_dir = target_dir.parent / f".{target_dir.name}.incoming-{work_id}"
        displaced_dir = target_dir.parent / f".{target_dir.name}.displaced-{work_id}"

        shutil.rmtree(incoming_dir, ignore_errors=True)
        shutil.copytree(source_dir, incoming_dir)

        target_existed = target_dir.exists()
        if target_existed:
            shutil.rmtree(backup_dir, ignore_errors=True)
            shutil.copytree(target_dir, backup_dir)

        try:
            if target_existed:
                os.replace(target_dir, displaced_dir)
            os.replace(incoming_dir, target_dir)
        except Exception as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            if displaced_dir.exists():
                os.replace(displaced_dir, target_dir)
            elif backup_dir.exists():
                shutil.copytree(backup_dir, target_dir)
            raise UpdateServiceError(
                "update.manifest_invalid",
                "Atomic component replacement failed",
                str(exc),
            ) from exc
        finally:
            shutil.rmtree(incoming_dir, ignore_errors=True)
            shutil.rmtree(displaced_dir, ignore_errors=True)

    def _set_job_fields(self, update_id: str, **fields: object) -> None:
        """Update top-level job fields under lock."""
        with self._lock:
            job = self._jobs[update_id]
            for key, value in fields.items():
                setattr(job, key, value)

    def _set_step(self, update_id: str, step_name: str, status: str, message: str = "") -> None:
        """Update one pipeline step status under lock."""
        with self._lock:
            job = self._jobs[update_id]
            step = job.steps[step_name]
            step.status = status
            step.message = message

    def _append_component_result(self, update_id: str, result: UpdateComponentResult) -> None:
        """Append component result under lock."""
        with self._lock:
            self._jobs[update_id].component_results.append(result)

    def _set_step_on_failure(self, update_id: str, exc: UpdateServiceError) -> None:
        """Mark active step as failed and append component-level failure when possible."""
        step_name = self._find_current_running_step(update_id) or STEP_VALIDATE_ARCHIVE
        self._set_step(update_id, step_name, "failed", exc.message)

        component = self._component_name_from_step(step_name)
        if component:
            self._append_component_result(
                update_id,
                UpdateComponentResult(
                    component=component,
                    action="failed",
                    message=exc.message,
                    error_code=exc.code,
                ),
            )

    def _finish_job(self, update_id: str) -> None:
        """Compute final status and stamp finish time."""
        with self._lock:
            job = self._jobs[update_id]
            failed = [item for item in job.component_results if item.action == "failed"]
            changed = [item for item in job.component_results if item.action in ("updated", "staged")]
            if failed and changed:
                job.status = "partial"
            elif failed:
                job.status = "failed"
            elif job.status not in ("failed", "partial"):
                job.status = "done"
            job.finished_at = _utc_now_iso()

    def _find_current_running_step(self, update_id: str) -> Optional[str]:
        """Return currently running step name, if any."""
        with self._lock:
            job = self._jobs[update_id]
            for step_name in STEP_ORDER:
                if job.steps[step_name].status == "running":
                    return step_name
        return None

    @staticmethod
    def _component_name_from_step(step_name: str) -> Optional[str]:
        """Translate step names to component names."""
        mapping = {
            STEP_APPLY_REST_API: "rest_api",
            STEP_APPLY_PYBEEP: "pybeep_vendor",
            STEP_STAGE_FIRMWARE: "firmware_bundle",
        }
        return mapping.get(step_name)


__all__ = [
    "UpdateService",
    "UpdateServiceError",
    "compute_directory_sha256",
    "compute_file_sha256",
]
