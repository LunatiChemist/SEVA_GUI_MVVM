"""Adapter and use-case wiring for the desktop app runtime.

This module owns lazy construction of concrete REST adapters and use-case
objects that depend on values in :class:`seva.viewmodels.settings_vm.SettingsVM`.
It is invoked by app-level presenters/controllers before network actions.
"""

from __future__ import annotations

from typing import Optional

from ..adapters.device_rest import DeviceRestAdapter
from ..adapters.firmware_rest import FirmwareRestAdapter
from ..adapters.job_rest import JobRestAdapter
from ..usecases.cancel_group import CancelGroup
from ..usecases.download_group_results import DownloadGroupResults
from ..usecases.flash_firmware import FlashFirmware
from ..usecases.poll_device_status import PollDeviceStatus
from ..usecases.poll_group_status import PollGroupStatus
from ..usecases.start_experiment_batch import StartExperimentBatch
from ..usecases.test_connection import TestConnection
from ..viewmodels.settings_vm import SettingsVM

try:
    from ..usecases.cancel_runs import CancelRuns as _CancelRunsClass
except ImportError:
    _CancelRunsClass = None


class AppController:
    """Create and cache runtime adapters/use-cases from settings state.

    Call chain:
        ``seva.app.main.App`` creates one instance and passes it to presenter
        and controller collaborators. Those collaborators call ``ensure_ready``
        before start/cancel/poll/download/test/flash operations.
    """

    def __init__(self, settings_vm: SettingsVM) -> None:
        """Initialize controller with settings-backed lazy dependencies.

        Args:
            settings_vm: UI state model containing API URLs, keys, and timeout
                preferences used to build adapter instances.
        """
        self.settings_vm = settings_vm
        self._job_adapter: Optional[JobRestAdapter] = None
        self._device_adapter: Optional[DeviceRestAdapter] = None
        self._firmware_adapter: Optional[FirmwareRestAdapter] = None
        self.uc_start: Optional[StartExperimentBatch] = None
        self.uc_poll: Optional[PollGroupStatus] = None
        self.uc_download: Optional[DownloadGroupResults] = None
        self.uc_cancel: Optional[CancelGroup] = None
        self.uc_cancel_runs: Optional["CancelRuns"] = None
        self.uc_poll_device_status: Optional[PollDeviceStatus] = None
        self.uc_test_connection: Optional[TestConnection] = None
        self.uc_flash_firmware: Optional[FlashFirmware] = None

    @property
    def job_adapter(self) -> Optional[JobRestAdapter]:
        """Return the cached job adapter used for run lifecycle requests."""
        return self._job_adapter

    @property
    def device_adapter(self) -> Optional[DeviceRestAdapter]:
        """Return the cached device adapter used for health/status requests."""
        return self._device_adapter

    def reset(self) -> None:
        """Drop all cached adapters and use-cases.

        Side Effects:
            Clears runtime objects so the next ``ensure_ready`` call rebuilds
            everything from current settings values.
        """
        self._job_adapter = None
        self._device_adapter = None
        self._firmware_adapter = None
        self.uc_start = None
        self.uc_poll = None
        self.uc_download = None
        self.uc_cancel = None
        self.uc_cancel_runs = None
        self.uc_poll_device_status = None
        self.uc_test_connection = None
        self.uc_flash_firmware = None

    def ensure_ready(self) -> bool:
        """Ensure adapters/use-cases are available for network operations.

        Returns:
            ``True`` when dependencies are available, ``False`` when required
            base URLs are missing from settings.
        """
        if (
            self._job_adapter
            and self._device_adapter
            and self._firmware_adapter
            and (self.uc_cancel_runs or _CancelRunsClass is None)
        ):
            return True

        base_urls = {k: v for k, v in (self.settings_vm.api_base_urls or {}).items() if v}
        if not base_urls:
            return False

        api_keys = {k: v for k, v in (self.settings_vm.api_keys or {}).items() if v}
        if self._job_adapter is None:
            self._job_adapter = JobRestAdapter(
                base_urls=base_urls,
                api_keys=api_keys,
                request_timeout_s=self.settings_vm.request_timeout_s,
                download_timeout_s=self.settings_vm.download_timeout_s,
                retries=2,
            )
            self.uc_poll = PollGroupStatus(self._job_adapter)
            self.uc_download = DownloadGroupResults(self._job_adapter)
            self.uc_cancel = CancelGroup(self._job_adapter)

        if _CancelRunsClass and self._job_adapter and self.uc_cancel_runs is None:
            self.uc_cancel_runs = _CancelRunsClass(self._job_adapter)

        if self._device_adapter is None:
            self._device_adapter = DeviceRestAdapter(
                base_urls=base_urls,
                api_keys=api_keys,
                request_timeout_s=self.settings_vm.request_timeout_s,
                retries=2,
            )

        if self._firmware_adapter is None:
            self._firmware_adapter = FirmwareRestAdapter(
                base_urls=base_urls,
                api_keys=api_keys,
                request_timeout_s=self.settings_vm.request_timeout_s,
                retries=2,
            )

        if self._job_adapter and self._device_adapter:
            self.uc_start = StartExperimentBatch(self._job_adapter)
            self.uc_test_connection = TestConnection(self._device_adapter)
            self.uc_poll_device_status = PollDeviceStatus(self._device_adapter)
        if self._firmware_adapter:
            self.uc_flash_firmware = FlashFirmware(self._firmware_adapter)
        return True

    def build_test_connection(
        self,
        *,
        box_id: str,
        base_url: str,
        api_key: str,
        request_timeout: int,
    ) -> TestConnection:
        """Create a one-box connection checker, optionally reusing adapter.

        Args:
            box_id: Target box identifier.
            base_url: Base URL to test.
            api_key: Optional API key for the box.
            request_timeout: Request timeout in seconds.

        Returns:
            A :class:`TestConnection` use-case bound to either a cached adapter
            (when target URL matches) or a temporary single-box adapter.
        """
        adapter = self._device_adapter
        if adapter and getattr(adapter, "base_urls", {}).get(box_id) == base_url:
            if self.uc_test_connection is None:
                self.uc_test_connection = TestConnection(adapter)
            return self.uc_test_connection

        api_map = {box_id: api_key} if api_key else {}
        device_port = DeviceRestAdapter(
            base_urls={box_id: base_url},
            api_keys=api_map,
            request_timeout_s=request_timeout,
            retries=0,
        )
        return TestConnection(device_port)
