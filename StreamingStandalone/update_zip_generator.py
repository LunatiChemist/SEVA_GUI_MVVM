"""Standalone GUI tool that creates remote-update package ZIP files."""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


@dataclass
class ComponentBuildResult:
    """Generated package artifact metadata for one component."""

    version: str
    package_path: str
    sha256: str
    flash_mode: str | None = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def _build_tar_from_folder(source_dir: Path, target_tar: Path) -> None:
    """Create gzipped TAR archive from folder contents."""
    with tarfile.open(target_tar, "w:gz") as archive:
        for item in sorted(source_dir.rglob("*")):
            arcname = item.relative_to(source_dir).as_posix()
            archive.add(item, arcname=arcname)


class UpdateZipGeneratorApp(tk.Tk):
    """Simple operator GUI for generating update-package ZIP files."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SEVA Update ZIP Generator")
        self.geometry("860x520")
        self.minsize(760, 460)

        now_stamp = datetime.now(timezone.utc).strftime("update-%Y%m%d-%H%M%S")
        self.package_id_var = tk.StringVar(value=now_stamp)
        self.created_by_var = tk.StringVar(value="zip-generator-gui")

        self.rest_api_dir_var = tk.StringVar(value="")
        self.rest_api_version_var = tk.StringVar(value="1.0.0")

        self.pybeep_dir_var = tk.StringVar(value="")
        self.pybeep_version_var = tk.StringVar(value="1.0.0")

        self.firmware_bin_var = tk.StringVar(value="")
        self.firmware_version_var = tk.StringVar(value="1.0.0")

        self.output_zip_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        pad = dict(padx=8, pady=6)
        self.columnconfigure(0, weight=1)

        meta = ttk.Labelframe(self, text="Manifest Metadata")
        meta.grid(row=0, column=0, sticky="ew", **pad)
        meta.columnconfigure(1, weight=1)
        ttk.Label(meta, text="package_id").grid(row=0, column=0, sticky="w")
        ttk.Entry(meta, textvariable=self.package_id_var).grid(row=0, column=1, sticky="ew")
        ttk.Label(meta, text="created_by").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(meta, textvariable=self.created_by_var).grid(row=1, column=1, sticky="ew", pady=(6, 0))

        rest_api = ttk.Labelframe(self, text="REST API Component (Optional)")
        rest_api.grid(row=1, column=0, sticky="ew", **pad)
        rest_api.columnconfigure(1, weight=1)
        ttk.Label(rest_api, text="Source folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(rest_api, textvariable=self.rest_api_dir_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(rest_api, text="Browse…", command=self._browse_rest_api).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(rest_api, text="Version").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(rest_api, textvariable=self.rest_api_version_var, width=20).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        pybeep = ttk.Labelframe(self, text="pyBEEP Component (Optional)")
        pybeep.grid(row=2, column=0, sticky="ew", **pad)
        pybeep.columnconfigure(1, weight=1)
        ttk.Label(pybeep, text="Source folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(pybeep, textvariable=self.pybeep_dir_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(pybeep, text="Browse…", command=self._browse_pybeep).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(pybeep, text="Version").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(pybeep, textvariable=self.pybeep_version_var, width=20).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        firmware = ttk.Labelframe(self, text="Firmware Component (Optional)")
        firmware.grid(row=3, column=0, sticky="ew", **pad)
        firmware.columnconfigure(1, weight=1)
        ttk.Label(firmware, text=".bin file").grid(row=0, column=0, sticky="w")
        ttk.Entry(firmware, textvariable=self.firmware_bin_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(firmware, text="Browse…", command=self._browse_firmware).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(firmware, text="Version").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(firmware, textvariable=self.firmware_version_var, width=20).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        output = ttk.Labelframe(self, text="Output")
        output.grid(row=4, column=0, sticky="ew", **pad)
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="ZIP file").grid(row=0, column=0, sticky="w")
        ttk.Entry(output, textvariable=self.output_zip_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(output, text="Choose…", command=self._browse_output).grid(row=0, column=2, padx=(6, 0))

        footer = ttk.Frame(self)
        footer.grid(row=5, column=0, sticky="ew", **pad)
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Generate Package", command=self._generate).grid(row=0, column=1, sticky="e")

    def _browse_rest_api(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Select REST API Source Folder")
        if selected:
            self.rest_api_dir_var.set(selected)

    def _browse_pybeep(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Select pyBEEP Source Folder")
        if selected:
            self.pybeep_dir_var.set(selected)

    def _browse_firmware(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Select Firmware Binary",
            filetypes=[("Firmware Binary", "*.bin"), ("All Files", "*.*")],
        )
        if selected:
            self.firmware_bin_var.set(selected)

    def _browse_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self,
            title="Select Output Update Package",
            defaultextension=".zip",
            filetypes=[("ZIP Package", "*.zip"), ("All Files", "*.*")],
        )
        if selected:
            self.output_zip_var.set(selected)

    def _generate(self) -> None:
        package_id = self.package_id_var.get().strip()
        created_by = self.created_by_var.get().strip()
        output_zip = self.output_zip_var.get().strip()
        if not package_id:
            messagebox.showerror("Validation", "package_id is required.", parent=self)
            return
        if not created_by:
            messagebox.showerror("Validation", "created_by is required.", parent=self)
            return
        if not output_zip:
            messagebox.showerror("Validation", "Output ZIP path is required.", parent=self)
            return

        rest_api_dir = Path(self.rest_api_dir_var.get().strip()) if self.rest_api_dir_var.get().strip() else None
        pybeep_dir = Path(self.pybeep_dir_var.get().strip()) if self.pybeep_dir_var.get().strip() else None
        firmware_bin = Path(self.firmware_bin_var.get().strip()) if self.firmware_bin_var.get().strip() else None

        try:
            with tempfile.TemporaryDirectory(prefix="seva_update_pkg_") as tmp_root:
                tmp = Path(tmp_root)
                components: dict[str, ComponentBuildResult] = {}

                if rest_api_dir:
                    if not rest_api_dir.is_dir():
                        raise ValueError(f"REST API source folder does not exist: {rest_api_dir}")
                    comp_dir = tmp / "rest_api"
                    comp_dir.mkdir(parents=True, exist_ok=True)
                    tar_path = comp_dir / "rest_api_bundle.tar.gz"
                    _build_tar_from_folder(rest_api_dir, tar_path)
                    components["rest_api"] = ComponentBuildResult(
                        version=self.rest_api_version_var.get().strip() or "0.0.0",
                        package_path="rest_api/rest_api_bundle.tar.gz",
                        sha256=_sha256_file(tar_path),
                    )

                if pybeep_dir:
                    if not pybeep_dir.is_dir():
                        raise ValueError(f"pyBEEP source folder does not exist: {pybeep_dir}")
                    comp_dir = tmp / "pybeep"
                    comp_dir.mkdir(parents=True, exist_ok=True)
                    tar_path = comp_dir / "pybeep_bundle.tar.gz"
                    _build_tar_from_folder(pybeep_dir, tar_path)
                    components["pybeep"] = ComponentBuildResult(
                        version=self.pybeep_version_var.get().strip() or "0.0.0",
                        package_path="pybeep/pybeep_bundle.tar.gz",
                        sha256=_sha256_file(tar_path),
                    )

                if firmware_bin:
                    if not firmware_bin.is_file():
                        raise ValueError(f"Firmware file does not exist: {firmware_bin}")
                    if firmware_bin.suffix.lower() != ".bin":
                        raise ValueError("Firmware file must be a .bin file.")
                    comp_dir = tmp / "firmware"
                    comp_dir.mkdir(parents=True, exist_ok=True)
                    target_name = firmware_bin.name
                    target_path = comp_dir / target_name
                    target_path.write_bytes(firmware_bin.read_bytes())
                    components["firmware"] = ComponentBuildResult(
                        version=self.firmware_version_var.get().strip() or "0.0.0",
                        package_path=f"firmware/{target_name}",
                        sha256=_sha256_file(target_path),
                        flash_mode="reuse_firmware_endpoint_logic",
                    )

                if not components:
                    raise ValueError("Select at least one component to include.")

                manifest_components: dict[str, dict[str, str]] = {}
                checksum_lines: list[str] = []
                for name, built in components.items():
                    if name in {"rest_api", "pybeep"}:
                        manifest_components[name] = {
                            "version": built.version,
                            "archive_path": built.package_path,
                            "sha256": built.sha256,
                        }
                    else:
                        manifest_components[name] = {
                            "version": built.version,
                            "bin_path": built.package_path,
                            "sha256": built.sha256,
                            "flash_mode": built.flash_mode or "reuse_firmware_endpoint_logic",
                        }
                    checksum_lines.append(f"{built.sha256}  {built.package_path}")

                manifest = {
                    "schema_version": "1.0",
                    "package_id": package_id,
                    "created_at_utc": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "created_by": created_by,
                    "components": manifest_components,
                }

                (tmp / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
                    encoding="utf-8",
                )
                (tmp / "checksums.sha256").write_text(
                    "\n".join(checksum_lines) + "\n",
                    encoding="utf-8",
                )

                output_path = Path(output_zip)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for item in sorted(tmp.rglob("*")):
                        if item.is_file():
                            archive.write(item, arcname=item.relative_to(tmp).as_posix())

            self.status_var.set(f"Created {output_zip}")
            messagebox.showinfo("Success", f"Update package created:\n{output_zip}", parent=self)
        except Exception as exc:
            self.status_var.set("Generation failed.")
            messagebox.showerror("Generation Failed", str(exc), parent=self)


def main() -> None:
    app = UpdateZipGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()

