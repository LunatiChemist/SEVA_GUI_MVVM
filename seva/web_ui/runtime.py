"""NiceGUI runtime orchestration for SEVA.

This module composes existing viewmodels and use cases for the web runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set
from urllib.parse import urlparse

import requests

from seva.adapters.discovery_http import HttpDiscoveryAdapter
from seva.adapters.relay_mock import RelayMock
from seva.adapters.storage_local import StorageLocal
from seva.app.controller import AppController
from seva.domain.ports import UseCaseError
from seva.domain.runs_registry import RunsRegistry
from seva.domain.storage_meta import StorageMeta
from seva.domain.util import well_id_to_box
from seva.usecases.build_experiment_plan import (
    BuildExperimentPlan,
    ExperimentPlanRequest,
    ModeSnapshot,
    WellSnapshot,
)
from seva.usecases.build_storage_meta import BuildStorageMeta
from seva.usecases.discover_and_assign_devices import (
    DiscoverAndAssignDevices,
    DiscoveryRequest,
)
from seva.usecases.discover_devices import DiscoverDevices, MergeDiscoveredIntoRegistry
from seva.usecases.load_plate_layout import LoadPlateLayout
from seva.usecases.run_flow_coordinator import FlowHooks, GroupContext, RunFlowCoordinator
from seva.usecases.save_plate_layout import SavePlateLayout
from seva.usecases.set_electrode_mode import SetElectrodeMode
from seva.usecases.start_experiment_batch import StartBatchResult
from seva.usecases.test_relay import TestRelay
from seva.viewmodels.experiment_vm import ExperimentVM
from seva.viewmodels.plate_vm import PlateVM
from seva.viewmodels.progress_vm import ProgressVM
from seva.viewmodels.runs_vm import RunRow, RunsVM
from seva.viewmodels.settings_vm import BOX_IDS, SettingsVM


LOGGER = logging.getLogger(__name__)

FORM_DEFAULTS: Dict[str, str] = {
    "run_cv": "0",
    "cv.vertex1_v": "",
    "cv.vertex2_v": "",
    "cv.final_v": "",
    "cv.scan_rate_v_s": "",
    "cv.cycles": "",
    "run_dc": "0",
    "run_ac": "0",
    "ea.duration_s": "",
    "ea.charge_cutoff_c": "",
    "ea.voltage_cutoff_v": "",
    "ea.frequency_hz": "",
    "control_mode": "current (mA)",
    "ea.target": "",
    "eval_cdl": "0",
    "cdl.vertex_a_v": "",
    "cdl.vertex_b_v": "",
    "run_eis": "0",
    "eis.freq_start_hz": "",
    "eis.freq_end_hz": "",
    "eis.points": "",
    "eis.spacing": "",
}


@dataclass
class RunSession:
    """Runtime state for one active group."""

    coordinator: RunFlowCoordinator
    context: GroupContext


class NasRestAdapter:
    """Simple NAS HTTP adapter used by the web runtime."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key or "")

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def setup(
        self,
        *,
        host: str,
        share: str,
        username: str,
        password: str,
        base_subdir: str,
        retention_days: int,
        domain: Optional[str],
    ) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/nas/setup",
            json={
                "host": host,
                "share": share,
                "username": username,
                "password": password,
                "base_subdir": base_subdir,
                "retention_days": int(retention_days),
                "domain": domain or None,
            },
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        return dict(response.json())

    def health(self) -> Dict[str, Any]:
        response = requests.get(
            f"{self.base_url}/nas/health",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return dict(response.json())

    def upload_run(self, run_id: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/runs/{run_id}/upload",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return dict(response.json())


class WebRuntime:
    """Orchestration state used by NiceGUI views."""

    def __init__(self) -> None:
        self.status_message = "Ready."
        self.last_download_dir: Optional[str] = None
        self.last_discovery_message = ""
        self.last_nas_response: Dict[str, Any] = {}
        self.discovery_rows: List[Dict[str, Any]] = []
        self.active_group_id: Optional[str] = None
        self.editing_well_label = "-"
        self.form_fields: Dict[str, str] = dict(FORM_DEFAULTS)

        self.runs = RunsRegistry.instance()
        self.plate_vm = PlateVM(on_selection_changed=self._on_selection_changed)
        self.experiment_vm = ExperimentVM()
        self.progress_vm = ProgressVM(
            on_update_run_overview=self._capture_overview,
            on_update_channel_activity=self._capture_activity,
        )
        self.settings_vm = SettingsVM()
        self.runs_vm = RunsVM(self.runs)

        self.latest_overview_dto: Dict[str, Any] = {
            "boxes": {},
            "wells": [],
            "activity": {},
            "updated_at": "",
        }
        self.latest_activity_map: Dict[str, str] = {}

        self.controller = AppController(self.settings_vm)
        self.storage = StorageLocal(root_dir=os.environ.get("SEVA_STORAGE_ROOT") or ".")

        self.uc_build_plan = BuildExperimentPlan()
        self.uc_build_storage_meta = BuildStorageMeta()
        self.uc_save_layout = SavePlateLayout(self.storage)
        self.uc_load_layout = LoadPlateLayout(self.storage)

        self._discovery_port = HttpDiscoveryAdapter(default_port=8000)
        self.uc_discover = DiscoverDevices(self._discovery_port)
        self.uc_merge_discovered = MergeDiscoveredIntoRegistry()
        self.uc_discover_assign = DiscoverAndAssignDevices(
            self.uc_discover,
            self.uc_merge_discovered,
        )

        self._relay = RelayMock()
        self.uc_test_relay = TestRelay(self._relay)
        self.uc_set_electrode_mode = SetElectrodeMode(self._relay)

        self._sessions: Dict[str, RunSession] = {}
        self._storage_meta: Dict[str, StorageMeta] = {}

        self._load_settings_defaults()
        self._configure_runs_registry()

    # ------------------------------------------------------------------
    # Basic projections
    # ------------------------------------------------------------------
    def run_rows(self) -> List[RunRow]:
        return self.runs_vm.rows()

    def settings_payload(self) -> Dict[str, Any]:
        return self.settings_vm.to_dict()

    def configured_boxes(self) -> List[str]:
        mapping = self.settings_vm.api_base_urls or {}
        boxes = [str(box) for box, url in mapping.items() if str(url or "").strip()]
        return sorted(boxes) if boxes else list(BOX_IDS)

    def configured_wells(self) -> Set[str]:
        return self.plate_vm.configured()

    def selection(self) -> Set[str]:
        return self.plate_vm.get_selection()

    def apply_settings_payload(self, payload: Mapping[str, Any]) -> None:
        self.settings_vm.apply_dict(payload)
        self.controller.reset()
        self.status_message = "Settings applied."

    def ensure_adapter(self) -> bool:
        if self.controller.ensure_ready():
            return True
        self.status_message = "Configure box URLs in Settings first."
        return False

    # ------------------------------------------------------------------
    # Settings workflows
    # ------------------------------------------------------------------
    def test_connection(self, box_id: str) -> Dict[str, Any]:
        box = str(box_id).strip().upper()
        url = str((self.settings_vm.api_base_urls or {}).get(box, "") or "").strip()
        if not url:
            raise UseCaseError("MISSING_URL", f"Box {box} URL is empty.")
        api_key = str((self.settings_vm.api_keys or {}).get(box, "") or "")
        uc = self.controller.build_test_connection(
            box_id=box,
            base_url=url,
            api_key=api_key,
            request_timeout=int(self.settings_vm.request_timeout_s),
        )
        return uc(box)

    def discover_devices(self) -> None:
        result = self.uc_discover_assign(
            DiscoveryRequest(
                candidates=self._build_discovery_candidates(),
                api_key=None,
                timeout_s=0.5,
                box_ids=BOX_IDS,
                existing_registry=self.settings_vm.api_base_urls or {},
            )
        )
        self.discovery_rows = [
            {
                "base_url": str(getattr(entry, "base_url", "") or "").strip(),
                "box_id": getattr(entry, "box_id", None),
                "build": getattr(entry, "build", None),
                "devices": getattr(entry, "devices", None),
            }
            for entry in result.discovered
        ]
        self.last_discovery_message = result.message
        if result.assigned:
            self.settings_vm.api_base_urls = result.normalized_registry
            self.controller.reset()
        self.status_message = result.message

    def test_relay(self) -> bool:
        return self.uc_test_relay(self.settings_vm.relay_ip, int(self.settings_vm.relay_port))

    # ------------------------------------------------------------------
    # Well/form workflows
    # ------------------------------------------------------------------
    def set_selection(self, wells: Iterable[str]) -> None:
        self.plate_vm.set_selection(wells)

    def toggle_select(self, well_id: str, *, additive: bool) -> None:
        selected = self.plate_vm.get_selection()
        if not additive:
            selected = {well_id}
        elif well_id in selected:
            selected.remove(well_id)
        else:
            selected.add(well_id)
        self.plate_vm.set_selection(selected)

    def set_form_field(self, field_id: str, value: Any) -> None:
        text = str(value if value is not None else "")
        self.form_fields[field_id] = text
        self.experiment_vm.set_field(field_id, text)

    def set_form_flag(self, field_id: str, enabled: bool) -> None:
        token = "1" if bool(enabled) else "0"
        self.form_fields[field_id] = token
        self.experiment_vm.set_field(field_id, token)

    def apply_params_to_selection(self) -> None:
        selected = self.plate_vm.get_selection()
        if not selected:
            raise UseCaseError("NO_SELECTION", "No wells selected.")
        for well_id in selected:
            self.experiment_vm.save_params_for(well_id, dict(self.form_fields))
        self.plate_vm.mark_configured(selected)
        self.status_message = "Parameters applied."

    def reset_selected_wells(self) -> None:
        selected = self.plate_vm.get_selection()
        if not selected:
            raise UseCaseError("NO_SELECTION", "No wells selected.")
        for well_id in selected:
            self.experiment_vm.clear_params_for(well_id)
        self.plate_vm.clear_configured(selected)
        self._on_selection_changed(selected)
        self.status_message = "Selected wells reset."

    def reset_all_wells(self) -> None:
        self.experiment_vm.clear_all_params()
        self.plate_vm.clear_all_configured()
        self.plate_vm.set_selection([])
        self.form_fields = dict(FORM_DEFAULTS)
        self.editing_well_label = "-"
        self.status_message = "All wells reset."

    def copy_mode(self, mode: str) -> None:
        selection = self.plate_vm.get_selection()
        if len(selection) != 1:
            raise UseCaseError("COPY_SELECTION", "Select exactly one well to copy.")
        source = next(iter(selection))
        snapshot = self.experiment_vm.build_mode_snapshot_for_copy(mode)
        if not snapshot:
            raise UseCaseError("COPY_EMPTY", "No parameters in form.")
        self.experiment_vm.cmd_copy_mode(mode, source, source_snapshot=snapshot)
        self.status_message = f"Copied {self.experiment_vm.mode_registry.label_for(mode)}."

    def paste_mode(self, mode: str) -> None:
        selection = self.plate_vm.get_selection()
        if not selection:
            raise UseCaseError("PASTE_SELECTION", "No wells selected.")
        self.experiment_vm.cmd_paste_mode(mode, selection)
        self.plate_vm.mark_configured(selection)
        self._on_selection_changed(selection)
        self.status_message = f"Pasted {self.experiment_vm.mode_registry.label_for(mode)}."

    def set_electrode_mode(self, mode: str) -> None:
        self.experiment_vm.set_electrode_mode(mode)
        self.uc_set_electrode_mode(mode)
        self.status_message = f"Electrode mode: {mode}"

    # ------------------------------------------------------------------
    # Layout workflows
    # ------------------------------------------------------------------
    def save_layout_payload(self, name: str) -> Path:
        selected = sorted(self.plate_vm.get_selection())
        return self.uc_save_layout(name, experiment_vm=self.experiment_vm, selection=selected)

    def load_layout_payload(self, name: str) -> Dict[str, Any]:
        data = self.uc_load_layout(
            name,
            experiment_vm=self.experiment_vm,
            plate_vm=self.plate_vm,
        )
        configured = self.plate_vm.configured()
        selection = list(data.get("selection") or sorted(configured))
        self.plate_vm.set_selection(selection)
        self.status_message = f"Loaded {name}"
        return data

    # ------------------------------------------------------------------
    # Run lifecycle workflows
    # ------------------------------------------------------------------
    def start_run(self) -> str:
        if not self.ensure_adapter():
            raise UseCaseError("MISSING_ADAPTER", "Configure box URLs first.")
        configured = self.plate_vm.configured()
        if not configured:
            raise UseCaseError("NO_CONFIGURED_WELLS", "No configured wells to start.")

        plan = self.uc_build_plan(self._build_plan_request(configured))
        storage_meta = self.uc_build_storage_meta(plan.meta, self.settings_vm)

        coordinator = RunFlowCoordinator(
            job_port=self.controller.job_adapter,
            storage_port=self.storage,
            uc_start=self.controller.uc_start,
            uc_poll=self.controller.uc_poll,
            uc_download=self.controller.uc_download,
            settings=self.settings_vm,
            hooks=FlowHooks(),
        )
        context = coordinator.start(plan, storage_meta)
        result = coordinator.last_start_result()
        if not isinstance(result, StartBatchResult):
            raise RuntimeError("Unexpected start result type.")

        group_id = str(context.group)
        self._storage_meta[group_id] = storage_meta
        self.runs.add(
            group_id=group_id,
            name=context.meta.experiment,
            boxes=sorted(result.per_box_runs.keys()),
            runs_by_box=result.per_box_runs,
            plan_meta=context.meta,
            storage_meta=storage_meta,
        )
        coordinator.hooks = self._build_hooks(group_id)
        self._sessions[group_id] = RunSession(coordinator=coordinator, context=context)
        self.runs.register_runtime(group_id, coordinator, context)
        self.select_group(group_id)
        self.status_message = f"Started group {group_id}."
        return group_id

    def poll_all_groups(self) -> None:
        for group_id in list(self._sessions.keys()):
            session = self._sessions.get(group_id)
            if not session or not self.ensure_adapter():
                continue
            tick = session.coordinator.poll_once(session.context)
            if tick.event == "completed":
                if tick.snapshot:
                    try:
                        session.coordinator.on_completed(session.context, tick.snapshot)
                    except Exception as exc:
                        self.status_message = f"Download failed: {exc}"
                self._finalize_group(group_id)
            elif tick.event == "error":
                self._finalize_group(group_id)

    def poll_device_activity(self) -> None:
        if not self.controller.ensure_ready() or not self.controller.uc_poll_device_status:
            return
        boxes = self.configured_boxes()
        if not boxes:
            return
        snapshot = self.controller.uc_poll_device_status(boxes)
        self.progress_vm.apply_device_activity(snapshot)

    def select_group(self, group_id: Optional[str]) -> None:
        self.active_group_id = group_id
        self.runs_vm.set_active_group(group_id)
        self.progress_vm.set_active_group(group_id, self.runs)

    def cancel_active_group(self) -> None:
        if not self.active_group_id:
            raise UseCaseError("NO_ACTIVE_GROUP", "No active group.")
        self.cancel_group(self.active_group_id)

    def cancel_group(self, group_id: str) -> None:
        if not self.ensure_adapter() or not self.controller.uc_cancel:
            raise UseCaseError("MISSING_ADAPTER", "Cancel use case unavailable.")
        gid = str(group_id).strip()
        if not gid:
            raise UseCaseError("INVALID_GROUP", "Group id is empty.")
        self.controller.uc_cancel(gid)
        self.runs.mark_cancelled(gid)
        self._finalize_group(gid)
        self.status_message = f"Cancel requested for {gid}."

    def cancel_selected_runs(self) -> None:
        selection = sorted(self.plate_vm.get_selection())
        if not selection:
            raise UseCaseError("NO_SELECTION", "Select at least one well.")
        if not self.ensure_adapter() or self.controller.uc_cancel_runs is None:
            raise UseCaseError("MISSING_ADAPTER", "Cancel selected runs unavailable.")
        box_runs = self.progress_vm.map_selection_to_runs(selection)
        if not box_runs:
            raise UseCaseError("NO_ACTIVE_RUNS", "Selected wells have no active runs.")
        self.controller.uc_cancel_runs(box_runs)
        self.status_message = "Abort requested for selected runs."

    def download_group_results(self, group_id: Optional[str] = None) -> str:
        if not self.ensure_adapter() or not self.controller.uc_download:
            raise UseCaseError("MISSING_ADAPTER", "Download use case unavailable.")
        gid = str(group_id or self.active_group_id or "").strip()
        if not gid:
            raise UseCaseError("NO_ACTIVE_GROUP", "No active group selected.")
        storage_meta = self.group_storage_meta_for(gid)
        if not storage_meta:
            raise UseCaseError("MISSING_STORAGE_META", "No storage metadata for selected group.")
        out_dir = self.controller.uc_download(
            gid,
            storage_meta.results_dir or self.settings_vm.results_dir,
            storage_meta,
            cleanup="archive",
        )
        self.last_download_dir = os.path.abspath(out_dir)
        self.status_message = f"Downloaded results for {gid}."
        return self.last_download_dir

    def delete_group(self, group_id: str) -> None:
        entry = self.runs.get(group_id)
        if not entry:
            return
        if entry.status in {"running", "pending"}:
            raise UseCaseError("GROUP_ACTIVE", "Cancel the group before deleting it.")
        self._finalize_group(group_id)
        self.runs.remove(group_id)
        if self.active_group_id == group_id:
            self.select_group(None)
        self.status_message = f"Removed {group_id}."

    # ------------------------------------------------------------------
    # Deferred workflows (firmware / NAS)
    # ------------------------------------------------------------------
    def persist_uploaded_firmware(self, filename: str, content: bytes) -> str:
        folder = Path(tempfile.gettempdir()) / "seva_web_uploads"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / Path(filename or "firmware.bin").name
        target.write_bytes(content)
        self.settings_vm.firmware_path = str(target)
        self.status_message = f"Firmware uploaded: {target.name}"
        return str(target)

    def flash_firmware(self):
        if not self.ensure_adapter() or self.controller.uc_flash_firmware is None:
            raise UseCaseError("MISSING_ADAPTER", "Firmware use case unavailable.")
        firmware_path = str(self.settings_vm.firmware_path or "").strip()
        if not firmware_path:
            raise UseCaseError("MISSING_FIRMWARE", "Select firmware file first.")
        result = self.controller.uc_flash_firmware(
            box_ids=self.configured_boxes(),
            firmware_path=firmware_path,
        )
        self.status_message = (
            "Firmware flash completed."
            if not result.failures
            else "Firmware flash completed with failures."
        )
        return result

    def nas_setup(
        self,
        *,
        box_id: str,
        host: str,
        share: str,
        username: str,
        password: str,
        base_subdir: str,
        retention_days: int,
        domain: Optional[str],
    ) -> Dict[str, Any]:
        payload = self._nas_adapter_for(box_id).setup(
            host=host,
            share=share,
            username=username,
            password=password,
            base_subdir=base_subdir,
            retention_days=retention_days,
            domain=domain,
        )
        self.last_nas_response = payload
        self.status_message = f"NAS setup applied on box {box_id}."
        return payload

    def nas_health(self, *, box_id: str) -> Dict[str, Any]:
        payload = self._nas_adapter_for(box_id).health()
        self.last_nas_response = payload
        self.status_message = f"NAS health read from box {box_id}."
        return payload

    def nas_upload_run(self, *, box_id: str, run_id: str) -> Dict[str, Any]:
        payload = self._nas_adapter_for(box_id).upload_run(run_id)
        self.last_nas_response = payload
        self.status_message = f"NAS upload enqueued on box {box_id}."
        return payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_settings_defaults(self) -> None:
        try:
            payload = self.storage.load_user_settings()
        except Exception as exc:
            LOGGER.warning("Could not load local settings defaults: %s", exc)
            return
        try:
            self.settings_vm.apply_dict(payload)
        except Exception as exc:
            LOGGER.warning("Could not apply local settings defaults: %s", exc)

    def _configure_runs_registry(self) -> None:
        self.runs.configure(
            store_path=Path.home() / ".seva" / "runs_registry.json",
            hooks_factory=self._build_hooks,
            coordinator_factory=self._coordinator_factory,
        )
        try:
            self.runs.load()
        except Exception as exc:
            LOGGER.warning("Could not load runs registry: %s", exc)
            return
        for group_id in self.runs.active_groups():
            try:
                context = self.runs.start_tracking(group_id)
            except Exception as exc:
                LOGGER.warning("Could not re-attach group %s: %s", group_id, exc)
                continue
            coordinator = self.runs.coordinator_for(group_id)
            if not coordinator or not context:
                continue
            self._sessions[group_id] = RunSession(coordinator=coordinator, context=context)
            self._storage_meta[group_id] = context.storage_meta

    def _coordinator_factory(self, group_id, plan_meta, storage_meta, hooks: FlowHooks):
        if not self.ensure_adapter():
            raise RuntimeError("Cannot attach coordinator without configured adapters.")
        return RunFlowCoordinator(
            job_port=self.controller.job_adapter,
            storage_port=self.storage,
            uc_start=self.controller.uc_start,
            uc_poll=self.controller.uc_poll,
            uc_download=self.controller.uc_download,
            settings=self.settings_vm,
            hooks=hooks,
        )

    def _build_hooks(self, group_id: str) -> FlowHooks:
        return FlowHooks(
            on_snapshot=lambda snapshot: self._on_group_snapshot(group_id, snapshot),
            on_completed=lambda path: self._on_group_completed(group_id, path),
            on_error=lambda message: self._on_group_error(group_id, message),
        )

    def _on_group_snapshot(self, group_id: str, snapshot: Any) -> None:
        self.runs.update_snapshot(group_id, snapshot)
        if group_id == self.active_group_id:
            self.progress_vm.apply_snapshot(snapshot)

    def _on_group_completed(self, group_id: str, path: Path) -> None:
        resolved = os.path.abspath(str(path))
        self.last_download_dir = resolved
        self.runs.mark_done(group_id, resolved)
        self.status_message = f"Group {group_id} completed."

    def _on_group_error(self, group_id: str, message: str) -> None:
        self.runs.mark_error(group_id, message)
        self.status_message = message or f"Polling failed for {group_id}."

    def _finalize_group(self, group_id: str) -> None:
        session = self._sessions.pop(group_id, None)
        if session:
            try:
                session.coordinator.stop_polling()
            except Exception:
                pass
        self.runs.unregister_runtime(group_id)
        if self.active_group_id == group_id:
            self.select_group(next(iter(self._sessions), None))

    def _capture_overview(self, dto: Dict[str, Any]) -> None:
        self.latest_overview_dto = dict(dto or {})

    def _capture_activity(self, mapping: Dict[str, str]) -> None:
        self.latest_activity_map = dict(mapping or {})

    def _on_selection_changed(self, selection: Set[str]) -> None:
        self.experiment_vm.set_selection(selection)
        if len(selection) != 1:
            self.editing_well_label = "-"
            self.form_fields = dict(FORM_DEFAULTS)
        else:
            well_id = next(iter(selection))
            self.editing_well_label = well_id
            snapshot = self.experiment_vm.get_params_for(well_id) or {}
            values = dict(FORM_DEFAULTS)
            values.update({str(k): str(v) for k, v in snapshot.items()})
            self.form_fields = values
        for field_id, value in self.form_fields.items():
            self.experiment_vm.set_field(field_id, value)

    def _build_plan_request(self, configured: Iterable[str]) -> ExperimentPlanRequest:
        wells = tuple(str(well) for well in configured)
        snapshots = []
        for well_id, modes in (self.experiment_vm.well_params or {}).items():
            mode_snapshots = tuple(
                ModeSnapshot(name=str(mode), params=dict(params))
                for mode, params in modes.items()
            )
            snapshots.append(WellSnapshot(well_id=str(well_id), modes=mode_snapshots))
        return ExperimentPlanRequest(
            experiment_name=str(getattr(self.settings_vm, "experiment_name", "") or ""),
            subdir=getattr(self.settings_vm, "subdir", None),
            client_datetime_override=str(self.form_fields.get("storage.client_datetime") or ""),
            wells=wells,
            well_snapshots=tuple(snapshots),
        )

    def _build_discovery_candidates(self) -> List[str]:
        candidates = []
        for url in (self.settings_vm.api_base_urls or {}).values():
            text = str(url or "").strip()
            if text:
                candidates.append(text)
        cidr_hints = []
        for value in candidates:
            host = urlparse(value).hostname or ""
            octets = host.split(".")
            if len(octets) != 4:
                continue
            try:
                if all(0 <= int(part) <= 255 for part in octets):
                    cidr_hints.append(".".join(octets[:3]) + ".0/24")
            except ValueError:
                continue
        ordered: List[str] = []
        seen: Set[str] = set()
        for value in [*candidates, *cidr_hints]:
            if value not in seen:
                seen.add(value)
                ordered.append(value)
        return ordered or ["192.168.0.0/24"]

    def group_storage_meta_for(self, group_id: str) -> Optional[StorageMeta]:
        meta = self._storage_meta.get(group_id)
        if meta:
            return meta
        entry = self.runs.get(group_id)
        return entry.storage_meta if entry else None

    def _nas_adapter_for(self, box_id: str) -> NasRestAdapter:
        box = str(box_id or "").strip().upper()
        if box not in BOX_IDS:
            raise UseCaseError("INVALID_BOX", f"Unknown box '{box_id}'.")
        base_url = str((self.settings_vm.api_base_urls or {}).get(box, "") or "").strip()
        if not base_url:
            raise UseCaseError("MISSING_URL", f"Box {box} URL is empty.")
        api_key = str((self.settings_vm.api_keys or {}).get(box, "") or "")
        return NasRestAdapter(base_url=base_url, api_key=api_key)
