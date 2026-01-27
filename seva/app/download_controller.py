from __future__ import annotations

"""Controller for download actions initiated from UI."""

import logging
import os
from typing import Callable

from seva.viewmodels.settings_vm import SettingsVM
from seva.app.controller import AppController
from seva.app.run_flow_presenter import RunFlowPresenter


class DownloadController:
    """Download orchestration for run results."""

    def __init__(
        self,
        *,
        win,
        controller: AppController,
        run_flow: RunFlowPresenter,
        settings_vm: SettingsVM,
        ensure_adapter: Callable[[], bool],
        toast_error,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self.win = win
        self.controller = controller
        self.run_flow = run_flow
        self.settings_vm = settings_vm
        self._ensure_adapter = ensure_adapter
        self._toast_error = toast_error

    def download_group_results(self) -> None:
        group_id = self.run_flow.active_group_id
        if not group_id or not self._ensure_adapter():
            self.win.show_toast("No active group.")
            return
        storage_meta = self.run_flow.group_storage_meta_for(group_id)
        if not storage_meta:
            self.win.show_toast(
                "Missing storage metadata for the active group. Start must finish before downloading."
            )
            return
        results_dir = storage_meta.results_dir or self.settings_vm.results_dir
        if not results_dir:
            self.win.show_toast("Results directory is not configured for downloads.")
            return
        try:
            out_dir = self.controller.uc_download(
                group_id,
                results_dir,
                storage_meta,
                cleanup="archive",
            )  # type: ignore[misc]
            self._log.info("Downloaded group %s to %s", group_id, out_dir)
            resolved_dir = os.path.abspath(out_dir)
            self.run_flow.record_download_dir(resolved_dir)
            self.win.show_toast(self.run_flow.build_download_toast(group_id, resolved_dir))
        except Exception as exc:
            self._toast_error(exc)

    def download_box_results(self, box_id: str) -> None:
        self.download_group_results()


__all__ = ["DownloadController"]
