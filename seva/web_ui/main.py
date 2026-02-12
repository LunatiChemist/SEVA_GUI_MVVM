"""NiceGUI entrypoint for SEVA web runtime."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable, Dict

from nicegui import ui

from seva.viewmodels.settings_vm import BOX_IDS
from seva.web_ui.plotter_vm import WebPlotterVM
from seva.web_ui.runtime import WebRuntime
from seva.web_ui.viewmodels import (
    BROWSER_SETTINGS_KEY,
    WebNasVM,
    WebSettingsVM,
    parse_settings_json,
)


def _install_theme() -> None:
    """Install global CSS/theme tokens for the web runtime."""
    ui.add_head_html(
        """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --seva-bg-a: #edf4ff;
  --seva-bg-b: #f9f1e8;
  --seva-card: rgba(255, 255, 255, 0.86);
  --seva-border: #c9d7e9;
  --seva-accent: #1d5d9b;
  --seva-accent-2: #0b8f8c;
  --seva-danger: #b42318;
  --seva-muted: #45556c;
}
body {
  font-family: 'Space Grotesk', sans-serif;
  background: radial-gradient(circle at top left, var(--seva-bg-a), var(--seva-bg-b));
}
.seva-page {
  max-width: 1480px;
  margin: 0 auto;
  padding: 14px;
  animation: slide-in 340ms ease-out;
}
.seva-card {
  background: var(--seva-card);
  border: 1px solid var(--seva-border);
  border-radius: 14px;
  backdrop-filter: blur(6px);
}
.seva-mono { font-family: 'IBM Plex Mono', monospace; }
.seva-chip {
  border: 1px solid var(--seva-border);
  border-radius: 8px;
  padding: 2px 8px;
  font-size: 12px;
}
@keyframes slide-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0px); }
}
</style>
        """
    )


def _notify_error(exc: Exception) -> None:
    """Render exceptions as concise NiceGUI toasts."""
    ui.notify(str(exc), color="negative", close_button="OK")


def _build_ui(runtime: WebRuntime) -> None:
    """Register the NiceGUI pages for the runtime."""

    @ui.page("/")
    async def index() -> None:
        settings_vm = WebSettingsVM.from_settings_vm(runtime.settings_vm)
        nas_vm = WebNasVM(box_id=runtime.configured_boxes()[0])
        plotter_vm = WebPlotterVM()
        additive_selection = {"enabled": False}
        layout_name = {"value": "layout_web.json"}

        settings_url_inputs: Dict[str, Any] = {}
        settings_key_inputs: Dict[str, Any] = {}
        settings_inputs: Dict[str, Any] = {}

        def sync_settings_inputs() -> None:
            """Push the settings VM values into form widgets."""
            for box in BOX_IDS:
                settings_url_inputs[box].value = settings_vm.api_base_urls.get(box, "")
                settings_key_inputs[box].value = settings_vm.api_keys.get(box, "")
            settings_inputs["request_timeout_s"].value = settings_vm.request_timeout_s
            settings_inputs["download_timeout_s"].value = settings_vm.download_timeout_s
            settings_inputs["poll_interval_ms"].value = settings_vm.poll_interval_ms
            settings_inputs["poll_backoff_max_ms"].value = settings_vm.poll_backoff_max_ms
            settings_inputs["results_dir"].value = settings_vm.results_dir
            settings_inputs["auto_download_on_complete"].value = settings_vm.auto_download_on_complete
            settings_inputs["experiment_name"].value = settings_vm.experiment_name
            settings_inputs["subdir"].value = settings_vm.subdir
            settings_inputs["use_streaming"].value = settings_vm.use_streaming
            settings_inputs["debug_logging"].value = settings_vm.debug_logging
            settings_inputs["relay_ip"].value = settings_vm.relay_ip
            settings_inputs["relay_port"].value = settings_vm.relay_port
            settings_inputs["firmware_path"].value = settings_vm.firmware_path

        @ui.refreshable
        def render_status() -> None:
            with ui.row().classes("w-full justify-between items-center seva-card p-3 q-mb-sm"):
                ui.label("SEVA NiceGUI Runtime").classes("text-h5")
                ui.label(runtime.status_message).classes("seva-mono text-caption")

        @ui.refreshable
        def render_well_grid() -> None:
            with ui.row().classes("w-full q-gutter-sm"):
                for box in runtime.configured_boxes():
                    with ui.card().classes("seva-card q-pa-sm"):
                        ui.label(f"Box {box}").classes("text-subtitle1")
                        for idx in range(1, 11):
                            number = idx + (ord(box) - ord("A")) * 10
                            well_id = f"{box}{number}"
                            selected = well_id in runtime.selection()
                            configured = well_id in runtime.configured_wells()
                            color = "primary" if selected else ("positive" if configured else "grey-5")
                            ui.button(
                                well_id,
                                color=color,
                                on_click=lambda _, w=well_id: on_well_click(w),
                            ).props("dense")

        @ui.refreshable
        def render_experiment_tab() -> None:
            with ui.column().classes("w-full"):
                ui.label(f"Editing well: {runtime.editing_well_label}")
                with ui.row().classes("q-gutter-sm"):
                    ui.checkbox(
                        "Additive selection",
                        value=additive_selection["enabled"],
                        on_change=lambda e: additive_selection.__setitem__("enabled", bool(e.value)),
                    )
                    ui.button("Apply Parameters", on_click=apply_params, color="primary")
                    ui.button("Reset Selected", on_click=reset_selected)
                    ui.button("Reset All", on_click=reset_all, color="warning")
                with ui.row().classes("q-gutter-sm"):
                    ui.select(
                        ["2E", "3E"],
                        value=runtime.experiment_vm.electrode_mode,
                        label="Electrode mode",
                        on_change=lambda e: set_electrode_mode(str(e.value)),
                    ).props("dense outlined")
                    ui.button("End Selection", on_click=cancel_selected)
                    ui.button("End Task", on_click=cancel_group, color="negative")

                ui.separator()
                mode_groups = [
                    (
                        "CV",
                        [("run_cv", "Run CV")],
                        [
                            ("cv.vertex1_v", "Vertex 1 vs. Ref (V)"),
                            ("cv.vertex2_v", "Vertex 2 vs. Ref (V)"),
                            ("cv.final_v", "Final vs. Ref (V)"),
                            ("cv.scan_rate_v_s", "Scan Rate (V/s)"),
                            ("cv.cycles", "Cycles"),
                        ],
                    ),
                    (
                        "DCAC",
                        [("run_dc", "Run DC"), ("run_ac", "Run AC")],
                        [
                            ("ea.duration_s", "Duration (s)"),
                            ("ea.charge_cutoff_c", "Charge cutoff (C)"),
                            ("ea.voltage_cutoff_v", "Voltage cutoff (V)"),
                            ("ea.frequency_hz", "Frequency (Hz)"),
                            ("control_mode", "Control mode"),
                            ("ea.target", "Target"),
                        ],
                    ),
                    (
                        "CDL",
                        [("eval_cdl", "Evaluate Cdl")],
                        [
                            ("cdl.vertex_a_v", "Vertex A vs. Ref (V)"),
                            ("cdl.vertex_b_v", "Vertex B vs. Ref (V)"),
                        ],
                    ),
                    (
                        "EIS",
                        [("run_eis", "Run EIS")],
                        [
                            ("eis.freq_start_hz", "Freq start (Hz)"),
                            ("eis.freq_end_hz", "Freq end (Hz)"),
                            ("eis.points", "Points"),
                            ("eis.spacing", "Spacing"),
                        ],
                    ),
                ]

                for mode_name, flags, fields in mode_groups:
                    with ui.card().classes("seva-card q-pa-sm"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(mode_name).classes("text-subtitle1")
                            with ui.row():
                                ui.button("Copy", on_click=lambda _, m=mode_name: copy_mode(m)).props("dense flat")
                                ui.button("Paste", on_click=lambda _, m=mode_name: paste_mode(m)).props("dense flat")
                        with ui.row().classes("q-gutter-sm"):
                            for field_id, label in flags:
                                checked = runtime.form_fields.get(field_id, "0") in {"1", "true", "True"}
                                ui.checkbox(
                                    label,
                                    value=checked,
                                    on_change=lambda e, f=field_id: on_flag_change(f, bool(e.value)),
                                )
                        with ui.row().classes("q-col-gutter-sm q-row-gutter-sm"):
                            for field_id, label in fields:
                                ui.input(
                                    label=label,
                                    value=runtime.form_fields.get(field_id, ""),
                                    on_change=lambda e, f=field_id: on_field_change(f, e.value),
                                ).props("outlined dense")

        @ui.refreshable
        def render_overview_tab() -> None:
            dto = runtime.latest_overview_dto or {}
            boxes = dto.get("boxes", {}) or {}
            with ui.row().classes("q-gutter-sm"):
                for box in runtime.configured_boxes():
                    meta = boxes.get(box, {})
                    with ui.card().classes("seva-card q-pa-sm"):
                        ui.label(f"Box {box}")
                        ui.label(f"Phase: {meta.get('phase', 'Idle')}").classes("seva-chip")
                        ui.label(f"Progress: {int(meta.get('progress', 0) or 0)}%")
                        subrun = meta.get("subrun")
                        ui.label(f"Subrun: {subrun}").classes("seva-mono text-caption")
            rows = []
            for row in dto.get("wells", []) or []:
                rows.append(
                    {
                        "well": row[0],
                        "phase": row[1],
                        "current_mode": row[2],
                        "next_modes": row[3],
                        "progress": row[4],
                        "remaining": row[5],
                        "error": row[6],
                        "subrun": row[7],
                    }
                )
            ui.table(
                columns=[
                    {"name": "well", "label": "Well", "field": "well"},
                    {"name": "phase", "label": "Phase", "field": "phase"},
                    {"name": "current_mode", "label": "Current", "field": "current_mode"},
                    {"name": "next_modes", "label": "Next", "field": "next_modes"},
                    {"name": "progress", "label": "Progress", "field": "progress"},
                    {"name": "remaining", "label": "Remaining", "field": "remaining"},
                    {"name": "error", "label": "Error", "field": "error"},
                    {"name": "subrun", "label": "Subrun", "field": "subrun"},
                ],
                rows=rows,
            ).classes("w-full")

        @ui.refreshable
        def render_activity_tab() -> None:
            ui.label(
                f"Updated at {runtime.latest_overview_dto.get('updated_at', '--:--:--')}"
            ).classes("seva-mono")
            with ui.row().classes("q-gutter-sm"):
                for box in runtime.configured_boxes():
                    with ui.card().classes("seva-card q-pa-sm"):
                        ui.label(f"Box {box}")
                        with ui.column().classes("q-gutter-xs"):
                            for idx in range(1, 11):
                                number = idx + (ord(box) - ord("A")) * 10
                                well_id = f"{box}{number}"
                                status = runtime.latest_activity_map.get(well_id, "Idle")
                                color = {
                                    "Running": "positive",
                                    "Queued": "warning",
                                    "Error": "negative",
                                    "Done": "primary",
                                }.get(status, "grey")
                                ui.badge(f"{well_id}: {status}", color=color)

        @ui.refreshable
        def render_runs_tab() -> None:
            rows = [
                {
                    "group_id": row.group_id,
                    "name": row.name,
                    "status": row.status,
                    "progress": row.progress,
                    "boxes": row.boxes,
                    "started_at": row.started_at,
                    "download_path": row.download_path,
                }
                for row in runtime.run_rows()
            ]
            ui.select(
                options=[row["group_id"] for row in rows],
                value=runtime.active_group_id,
                label="Active group",
                on_change=lambda e: runtime.select_group(str(e.value) if e.value else None),
            ).props("dense outlined")
            with ui.row().classes("q-gutter-sm"):
                ui.button("Cancel Group", on_click=cancel_group, color="negative")
                ui.button("Delete Group", on_click=delete_group, color="warning")
                ui.button("Download Results", on_click=download_results)
            ui.table(
                columns=[
                    {"name": "group_id", "label": "Group", "field": "group_id"},
                    {"name": "name", "label": "Name", "field": "name"},
                    {"name": "status", "label": "Status", "field": "status"},
                    {"name": "progress", "label": "Progress", "field": "progress"},
                    {"name": "boxes", "label": "Boxes", "field": "boxes"},
                    {"name": "started_at", "label": "Started", "field": "started_at"},
                    {"name": "download_path", "label": "Download path", "field": "download_path"},
                ],
                rows=rows,
            ).classes("w-full")

        @ui.refreshable
        def render_discovery_rows() -> None:
            ui.label(runtime.last_discovery_message or "No discovery executed yet.")
            ui.table(
                columns=[
                    {"name": "base_url", "label": "Base URL", "field": "base_url"},
                    {"name": "box_id", "label": "Box ID", "field": "box_id"},
                    {"name": "build", "label": "Build", "field": "build"},
                    {"name": "devices", "label": "Devices", "field": "devices"},
                ],
                rows=runtime.discovery_rows,
            ).classes("w-full")

        @ui.refreshable
        def render_nas_response() -> None:
            with ui.card().classes("seva-card q-pa-sm"):
                ui.label("NAS response").classes("text-subtitle2")
                ui.code(json.dumps(runtime.last_nas_response or {}, indent=2), language="json")

        @ui.refreshable
        def render_plotter_chart() -> None:
            ui.label(plotter_vm.filename or "No CSV loaded")
            if not plotter_vm.columns:
                return
            with ui.row().classes("q-gutter-sm"):
                ui.select(
                    plotter_vm.numeric_columns,
                    value=plotter_vm.x_column,
                    label="X axis",
                    on_change=lambda e: set_plot_axis("x", str(e.value)),
                )
                ui.select(
                    plotter_vm.numeric_columns,
                    value=plotter_vm.y_column,
                    label="Y axis",
                    on_change=lambda e: set_plot_axis("y", str(e.value)),
                )
                ui.select(
                    plotter_vm.numeric_columns,
                    value=plotter_vm.y2_column,
                    label="Y2 axis",
                    on_change=lambda e: set_plot_axis("y2", str(e.value)),
                )
                ui.checkbox(
                    "Show Y2",
                    value=plotter_vm.show_y2,
                    on_change=lambda e: toggle_plot_y2(bool(e.value)),
                )
            ui.echart(plotter_vm.chart_options()).classes("w-full h-96")

        def refresh_runtime_views() -> None:
            render_status.refresh()
            render_well_grid.refresh()
            render_experiment_tab.refresh()
            render_overview_tab.refresh()
            render_activity_tab.refresh()
            render_runs_tab.refresh()

        def on_well_click(well_id: str) -> None:
            runtime.toggle_select(well_id, additive=additive_selection["enabled"])
            render_well_grid.refresh()
            render_experiment_tab.refresh()

        def on_field_change(field_id: str, value: Any) -> None:
            runtime.set_form_field(field_id, value)

        def on_flag_change(field_id: str, value: bool) -> None:
            runtime.set_form_flag(field_id, value)

        def _invoke(action: Callable[[], Any], *refreshers: Callable[[], None]) -> None:
            try:
                action()
            except Exception as exc:
                _notify_error(exc)
                render_status.refresh()
                return
            for refresh in refreshers:
                refresh()

        def apply_params() -> None:
            _invoke(runtime.apply_params_to_selection, render_well_grid.refresh, render_status.refresh)

        def reset_selected() -> None:
            _invoke(
                runtime.reset_selected_wells,
                render_well_grid.refresh,
                render_experiment_tab.refresh,
                render_status.refresh,
            )

        def reset_all() -> None:
            _invoke(
                runtime.reset_all_wells,
                render_well_grid.refresh,
                render_experiment_tab.refresh,
                render_status.refresh,
            )

        def copy_mode(mode: str) -> None:
            _invoke(lambda: runtime.copy_mode(mode), render_status.refresh)

        def paste_mode(mode: str) -> None:
            _invoke(
                lambda: runtime.paste_mode(mode),
                render_well_grid.refresh,
                render_experiment_tab.refresh,
                render_status.refresh,
            )

        def set_electrode_mode(mode: str) -> None:
            _invoke(lambda: runtime.set_electrode_mode(mode), render_status.refresh)

        def cancel_selected() -> None:
            _invoke(runtime.cancel_selected_runs, render_status.refresh, render_runs_tab.refresh)

        def start_run() -> None:
            _invoke(runtime.start_run, refresh_runtime_views)

        def cancel_group() -> None:
            _invoke(runtime.cancel_active_group, refresh_runtime_views)

        def delete_group() -> None:
            _invoke(lambda: runtime.delete_group(str(runtime.active_group_id or "")), refresh_runtime_views)

        def download_results() -> None:
            _invoke(runtime.download_group_results, render_status.refresh, render_runs_tab.refresh)

        def save_layout() -> None:
            _invoke(lambda: runtime.save_layout_payload(layout_name["value"]), render_status.refresh)

        def load_layout() -> None:
            _invoke(
                lambda: runtime.load_layout_payload(layout_name["value"]),
                render_well_grid.refresh,
                render_experiment_tab.refresh,
                render_status.refresh,
            )

        def run_discovery() -> None:
            def action() -> None:
                nonlocal settings_vm
                runtime.apply_settings_payload(settings_vm.to_payload())
                runtime.discover_devices()
                settings_vm = WebSettingsVM.from_settings_vm(runtime.settings_vm)
                sync_settings_inputs()
            _invoke(action, render_status.refresh, render_discovery_rows.refresh)

        def run_test_connection(box: str) -> None:
            def action() -> None:
                runtime.apply_settings_payload(settings_vm.to_payload())
                result = runtime.test_connection(box)
                state = "ok" if result.get("ok") else "failed"
                ui.notify(f"Box {box}: {state}", color="positive" if state == "ok" else "warning")
            _invoke(action, render_status.refresh)

        def run_test_relay() -> None:
            def action() -> None:
                runtime.apply_settings_payload(settings_vm.to_payload())
                ok = runtime.test_relay()
                ui.notify("Relay test successful." if ok else "Relay test failed.", color="positive" if ok else "warning")
            _invoke(action, render_status.refresh)

        async def save_settings_to_browser() -> None:
            try:
                payload = settings_vm.to_payload()
                runtime.apply_settings_payload(payload)
                dumped = json.dumps(payload, ensure_ascii=False)
                await ui.run_javascript(
                    f"localStorage.setItem({json.dumps(BROWSER_SETTINGS_KEY)}, {json.dumps(dumped)});"
                )
                ui.notify("Settings saved to browser storage.", color="positive")
            except Exception as exc:
                _notify_error(exc)
            refresh_runtime_views()

        async def load_settings_from_browser() -> None:
            nonlocal settings_vm
            try:
                raw = await ui.run_javascript(
                    f"return localStorage.getItem({json.dumps(BROWSER_SETTINGS_KEY)}) || '';"
                )
                text = str(raw or "").strip()
                if not text:
                    ui.notify("No browser settings found.", color="warning")
                    return
                payload = parse_settings_json(text)
                runtime.apply_settings_payload(payload)
                settings_vm = WebSettingsVM.from_settings_vm(runtime.settings_vm)
                sync_settings_inputs()
                ui.notify("Loaded settings from browser storage.", color="positive")
            except Exception as exc:
                _notify_error(exc)
            refresh_runtime_views()

        def export_settings_json() -> None:
            payload = settings_vm.to_payload()
            ui.download(
                json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                filename="seva_settings.json",
            )

        def on_import_settings(event) -> None:
            nonlocal settings_vm
            try:
                text = event.content.read().decode("utf-8-sig")
                payload = parse_settings_json(text)
                runtime.apply_settings_payload(payload)
                settings_vm = WebSettingsVM.from_settings_vm(runtime.settings_vm)
                sync_settings_inputs()
                dumped = json.dumps(payload, ensure_ascii=False)
                ui.run_javascript(
                    f"localStorage.setItem({json.dumps(BROWSER_SETTINGS_KEY)}, {json.dumps(dumped)});"
                )
                ui.notify("Imported settings JSON.", color="positive")
            except Exception as exc:
                _notify_error(exc)
            refresh_runtime_views()

        def upload_firmware(event) -> None:
            def action() -> None:
                path = runtime.persist_uploaded_firmware(event.name, event.content.read())
                settings_vm.firmware_path = path
                settings_inputs["firmware_path"].value = path
            _invoke(action, render_status.refresh)

        def flash_firmware() -> None:
            def action() -> None:
                runtime.apply_settings_payload(settings_vm.to_payload())
                result = runtime.flash_firmware()
                if result.failures:
                    ui.notify(f"Firmware failures: {', '.join(sorted(result.failures.keys()))}", color="warning")
                else:
                    ui.notify("Firmware flashed successfully.", color="positive")
            _invoke(action, render_status.refresh)

        def run_nas_setup() -> None:
            _invoke(
                lambda: runtime.nas_setup(
                    box_id=nas_vm.box_id,
                    host=nas_vm.host,
                    share=nas_vm.share,
                    username=nas_vm.username,
                    password=nas_vm.password,
                    base_subdir=nas_vm.base_subdir,
                    retention_days=nas_vm.retention_days,
                    domain=nas_vm.domain or None,
                ),
                render_status.refresh,
                render_nas_response.refresh,
            )

        def run_nas_health() -> None:
            _invoke(
                lambda: runtime.nas_health(box_id=nas_vm.box_id),
                render_status.refresh,
                render_nas_response.refresh,
            )

        def run_nas_upload() -> None:
            _invoke(
                lambda: runtime.nas_upload_run(box_id=nas_vm.box_id, run_id=nas_vm.run_id),
                render_status.refresh,
                render_nas_response.refresh,
            )

        def on_plotter_upload(event) -> None:
            try:
                plotter_vm.load_csv_bytes(event.content.read(), filename=event.name)
                render_plotter_chart.refresh()
            except Exception as exc:
                _notify_error(exc)

        def set_plot_axis(axis: str, value: str) -> None:
            if axis == "x":
                plotter_vm.x_column = value
            elif axis == "y":
                plotter_vm.y_column = value
            else:
                plotter_vm.y2_column = value
            render_plotter_chart.refresh()

        def toggle_plot_y2(enabled: bool) -> None:
            plotter_vm.show_y2 = bool(enabled)
            render_plotter_chart.refresh()

        def export_plotter_csv() -> None:
            try:
                data = plotter_vm.export_csv_bytes()
            except Exception as exc:
                _notify_error(exc)
                return
            ui.download(data, filename=plotter_vm.filename or "plotter_export.csv")

        with ui.column().classes("seva-page w-full"):
            render_status()
            with ui.row().classes("w-full q-gutter-sm items-end"):
                ui.button("Start", on_click=start_run, color="primary")
                ui.button("Cancel Group", on_click=cancel_group, color="negative")
                ui.button("Download Results", on_click=download_results)
                ui.input(
                    "Layout file",
                    value=layout_name["value"],
                    on_change=lambda e: layout_name.__setitem__("value", str(e.value)),
                ).props("dense outlined").classes("w-64")
                ui.button("Save Layout", on_click=save_layout).props("outline")
                ui.button("Load Layout", on_click=load_layout).props("outline")

            with ui.tabs().classes("w-full") as tabs:
                tab_plate = ui.tab("Plate")
                tab_experiment = ui.tab("Experiment")
                tab_overview = ui.tab("Run Overview")
                tab_activity = ui.tab("Channel Activity")
                tab_runs = ui.tab("Runs")
                tab_settings = ui.tab("Settings")
                tab_firmware = ui.tab("Firmware")
                tab_nas = ui.tab("NAS")
                tab_plotter = ui.tab("Data Plotter")

            with ui.tab_panels(tabs, value=tab_plate).classes("w-full"):
                with ui.tab_panel(tab_plate):
                    render_well_grid()
                with ui.tab_panel(tab_experiment):
                    render_experiment_tab()
                with ui.tab_panel(tab_overview):
                    render_overview_tab()
                with ui.tab_panel(tab_activity):
                    render_activity_tab()
                with ui.tab_panel(tab_runs):
                    render_runs_tab()
                with ui.tab_panel(tab_settings):
                    with ui.column().classes("w-full q-gutter-sm"):
                        with ui.card().classes("seva-card q-pa-sm"):
                            ui.label("Box API configuration")
                            for box in BOX_IDS:
                                with ui.row().classes("w-full items-center q-gutter-sm"):
                                    ui.label(f"Box {box}").classes("w-16")
                                    settings_url_inputs[box] = ui.input(
                                        "Base URL",
                                        value=settings_vm.api_base_urls.get(box, ""),
                                        on_change=lambda e, b=box: settings_vm.api_base_urls.__setitem__(b, str(e.value or "").strip()),
                                    ).props("dense outlined").classes("w-72")
                                    settings_key_inputs[box] = ui.input(
                                        "API key",
                                        value=settings_vm.api_keys.get(box, ""),
                                        password=True,
                                        on_change=lambda e, b=box: settings_vm.api_keys.__setitem__(b, str(e.value or "")),
                                    ).props("dense outlined").classes("w-56")
                                    ui.button("Test", on_click=lambda _, b=box: run_test_connection(b)).props("dense")
                            ui.button("Scan Network", on_click=run_discovery).props("outline")
                            render_discovery_rows()

                        with ui.card().classes("seva-card q-pa-sm"):
                            ui.label("Runtime and storage")
                            with ui.row().classes("q-gutter-sm"):
                                settings_inputs["request_timeout_s"] = ui.number("Request timeout (s)", value=settings_vm.request_timeout_s, on_change=lambda e: setattr(settings_vm, "request_timeout_s", int(e.value or 10))).props("dense outlined")
                                settings_inputs["download_timeout_s"] = ui.number("Download timeout (s)", value=settings_vm.download_timeout_s, on_change=lambda e: setattr(settings_vm, "download_timeout_s", int(e.value or 60))).props("dense outlined")
                                settings_inputs["poll_interval_ms"] = ui.number("Poll interval (ms)", value=settings_vm.poll_interval_ms, on_change=lambda e: setattr(settings_vm, "poll_interval_ms", int(e.value or 750))).props("dense outlined")
                                settings_inputs["poll_backoff_max_ms"] = ui.number("Poll backoff max (ms)", value=settings_vm.poll_backoff_max_ms, on_change=lambda e: setattr(settings_vm, "poll_backoff_max_ms", int(e.value or 5000))).props("dense outlined")
                            settings_inputs["results_dir"] = ui.input("Results directory", value=settings_vm.results_dir, on_change=lambda e: setattr(settings_vm, "results_dir", str(e.value or "."))).props("dense outlined").classes("w-80")
                            settings_inputs["experiment_name"] = ui.input("Experiment name", value=settings_vm.experiment_name, on_change=lambda e: setattr(settings_vm, "experiment_name", str(e.value or ""))).props("dense outlined").classes("w-80")
                            settings_inputs["subdir"] = ui.input("Subdirectory", value=settings_vm.subdir, on_change=lambda e: setattr(settings_vm, "subdir", str(e.value or ""))).props("dense outlined").classes("w-80")
                            settings_inputs["auto_download_on_complete"] = ui.checkbox("Auto-download on completion", value=settings_vm.auto_download_on_complete, on_change=lambda e: setattr(settings_vm, "auto_download_on_complete", bool(e.value)))
                            settings_inputs["use_streaming"] = ui.checkbox("Use streaming flag", value=settings_vm.use_streaming, on_change=lambda e: setattr(settings_vm, "use_streaming", bool(e.value)))
                            settings_inputs["debug_logging"] = ui.checkbox("Enable debug logging", value=settings_vm.debug_logging, on_change=lambda e: setattr(settings_vm, "debug_logging", bool(e.value)))
                            settings_inputs["relay_ip"] = ui.input("Relay IP", value=settings_vm.relay_ip, on_change=lambda e: setattr(settings_vm, "relay_ip", str(e.value or ""))).props("dense outlined").classes("w-64")
                            settings_inputs["relay_port"] = ui.number("Relay port", value=settings_vm.relay_port, on_change=lambda e: setattr(settings_vm, "relay_port", int(e.value or 0))).props("dense outlined").classes("w-40")
                            settings_inputs["firmware_path"] = ui.input("Firmware path", value=settings_vm.firmware_path, on_change=lambda e: setattr(settings_vm, "firmware_path", str(e.value or ""))).props("dense outlined").classes("w-96")
                            with ui.row().classes("q-gutter-sm"):
                                ui.button("Test Relay", on_click=run_test_relay)
                                ui.button("Save to Browser", on_click=save_settings_to_browser, color="primary")
                                ui.button("Load from Browser", on_click=load_settings_from_browser)
                                ui.button("Export JSON", on_click=export_settings_json)
                                ui.upload(on_upload=on_import_settings, auto_upload=True, label="Import JSON")

                with ui.tab_panel(tab_firmware):
                    with ui.column().classes("w-full q-gutter-sm"):
                        ui.upload(on_upload=upload_firmware, auto_upload=True, label="Upload firmware .bin")
                        ui.button("Flash Firmware to Configured Boxes", on_click=flash_firmware, color="warning")
                with ui.tab_panel(tab_nas):
                    with ui.column().classes("w-full q-gutter-sm"):
                        ui.select(list(BOX_IDS), value=nas_vm.box_id, label="Target box", on_change=lambda e: setattr(nas_vm, "box_id", str(e.value)))
                        nas_host = ui.input("Host", value=nas_vm.host, on_change=lambda e: setattr(nas_vm, "host", str(e.value or "")))
                        nas_share = ui.input("Share", value=nas_vm.share, on_change=lambda e: setattr(nas_vm, "share", str(e.value or "")))
                        nas_user = ui.input("Username", value=nas_vm.username, on_change=lambda e: setattr(nas_vm, "username", str(e.value or "")))
                        nas_pass = ui.input("Password", value=nas_vm.password, password=True, on_change=lambda e: setattr(nas_vm, "password", str(e.value or "")))
                        nas_subdir = ui.input("Base subdir", value=nas_vm.base_subdir, on_change=lambda e: setattr(nas_vm, "base_subdir", str(e.value or "")))
                        nas_ret = ui.number("Retention days", value=nas_vm.retention_days, on_change=lambda e: setattr(nas_vm, "retention_days", int(e.value or 14)))
                        nas_domain = ui.input("Domain (optional)", value=nas_vm.domain, on_change=lambda e: setattr(nas_vm, "domain", str(e.value or "")))
                        nas_run = ui.input("Run id (for upload)", value=nas_vm.run_id, on_change=lambda e: setattr(nas_vm, "run_id", str(e.value or "")))
                        with ui.row().classes("q-gutter-sm"):
                            ui.button("Setup NAS", on_click=run_nas_setup)
                            ui.button("NAS Health", on_click=run_nas_health)
                            ui.button("Upload Run", on_click=run_nas_upload)
                        render_nas_response()
                with ui.tab_panel(tab_plotter):
                    with ui.column().classes("w-full q-gutter-sm"):
                        ui.upload(on_upload=on_plotter_upload, auto_upload=True, label="Upload CSV")
                        ui.button("Export Current CSV", on_click=export_plotter_csv)
                        render_plotter_chart()

            sync_settings_inputs()
            await load_settings_from_browser()

            def periodic_refresh() -> None:
                runtime.poll_all_groups()
                runtime.poll_device_activity()
                render_status.refresh()
                render_overview_tab.refresh()
                render_activity_tab.refresh()
                render_runs_tab.refresh()

            ui.timer(2.0, periodic_refresh)


def _parse_args() -> argparse.Namespace:
    """Parse CLI args for web runtime startup."""
    parser = argparse.ArgumentParser(description="Run SEVA NiceGUI web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint for the NiceGUI runtime."""
    args = _parse_args()
    runtime = WebRuntime()
    if args.smoke_test:
        payload = runtime.settings_payload()
        print("web-smoke-ok", sorted(payload.get("api_base_urls", {}).keys()))
        return
    _install_theme()
    _build_ui(runtime)
    ui.run(
        host=args.host,
        port=args.port,
        title="SEVA Web UI",
        reload=args.reload,
        show=False,
        storage_secret=os.environ.get("SEVA_WEB_STORAGE_SECRET", "seva-web-ui-secret"),
    )


if __name__ == "__main__":
    main()
