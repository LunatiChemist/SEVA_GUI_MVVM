# Modernize all Tkinter views with a cohesive desktop design system

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agent/PLANS.md` and must be maintained in accordance with its requirements.

## Purpose / Big Picture

The current SEVA desktop UI is functionally complete but visually dated and inconsistent across tabs/dialogs. After this change, users can run the same workflows with a cleaner, modern appearance: unified spacing, typography, buttons, cards, and table styling. The behavior remains unchanged and MVVM boundaries remain strict because edits are isolated to view modules.

A user should observe the change by running the desktop app and seeing: a modern toolbar hierarchy, cleaner split layout, styled tabs/tables, and more polished well/activity cells.

## Progress

- [x] (2026-02-12 00:00Z) Reviewed AGENTS guardrails and `.agent/PLANS.md` requirements.
- [x] (2026-02-12 00:35Z) Implemented shared theme module and wired it at app root window initialization.
- [x] (2026-02-12 00:40Z) Refreshed main window layout structure and status bar visuals.
- [x] (2026-02-12 00:52Z) Modernized tab views and dialogs while keeping callback contracts intact.
- [x] (2026-02-12 00:55Z) Ran compile and focused test checks successfully.

## Surprises & Discoveries

- Observation: Several views still rely on `tk.Button`/`tk.Label` so ttk theme changes alone are insufficient for status-like colored cells.
  Evidence: `seva/app/views/well_grid_view.py` and `seva/app/views/channel_activity_view.py` use direct background colors to represent state.

## Decision Log

- Decision: Introduce a dedicated `seva/app/views/theme.py` module and call it from `MainWindowView`.
  Rationale: Keeps style concerns centralized and reusable while preserving all existing callback contracts.
  Date/Author: 2026-02-12 / Codex

- Decision: Keep semantic state colors for wells/channel activity in tk widgets, but align palette and typography with the new theme.
  Rationale: These widgets need direct background color mutation and are already stable with current API.
  Date/Author: 2026-02-12 / Codex

## Outcomes & Retrospective

The UI now uses a centralized theme and updated spacing/card hierarchy across main tabs and dialogs. All existing callbacks and view APIs stayed intact so composition in `seva/app/main.py` remains unchanged.

Validation passed with `python -m compileall seva/app/views` and `pytest -q seva/tests/test_mode_registry.py`. No behavior-level regressions were introduced in tested scope.

## Context and Orientation

The app entrypoint composition root is `seva/app/main.py`, which creates a `MainWindowView` and mounts all tab views and dialogs. The UI is Tkinter-based and follows MVVM + Hexagonal boundaries where views only emit callback intents. Relevant files:

- `seva/app/views/main_window.py`: root shell with toolbar, split area, tabs, and status bar.
- `seva/app/views/well_grid_view.py`: selectable well matrix (colored cells).
- `seva/app/views/experiment_panel_view.py`: experiment parameter form blocks.
- `seva/app/views/run_overview_view.py`: summary cards + table.
- `seva/app/views/channel_activity_view.py`: status matrix with color legend.
- `seva/app/views/runs_panel_view.py`: runs registry table and actions.
- `seva/app/views/settings_dialog.py`: modal settings editor.
- `seva/app/views/discovery_results_dialog.py`: modal discovery results table.

No business logic or adapter orchestration may be added in these files.

## Plan of Work

Create a shared theme module that defines colors, ttk style names, paddings, and treeview/notebook/button defaults. Apply it in the main window constructor early so every view inherits it.

Then update individual views to use semantic container frames (toolbar cards, section cards) and consistent paddings/spacings. Preserve all public methods and callback signatures. When replacing placeholder widgets, keep parent-child relationships intact so `App` mounting logic in `seva/app/main.py` remains valid.

For colored cell widgets (well grid and channel activity), keep direct color updates but refresh palette and dimensions to look modern. Add optional legends where useful.

## Concrete Steps

Run from repository root `/workspace/SEVA_GUI_MVVM`.

1. Implement `seva/app/views/theme.py` with an `apply_modern_theme(root: tk.Misc)` helper.
2. Import and call `apply_modern_theme` in `MainWindowView.__init__` before constructing child widgets.
3. Refactor the main window toolbar/main split/status bar spacing and styles.
4. Update each major view module with style usage and improved layout density.
5. Execute checks:

   python -m compileall seva/app/views

6. Execute focused tests (if present and quick):

   pytest -q seva/tests/test_mode_registry.py

## Validation and Acceptance

Acceptance is met when:

- App still boots without callback/signature regressions.
- Compile/test commands succeed.
- View modules render with visibly modernized layout and style semantics.

Manual run command:

  python -m seva.app.main

Expected result: main window opens with updated visual hierarchy and all tabs present.

## Idempotence and Recovery

Edits are limited to view modules and a new theme helper. Re-running steps is safe. If a style change causes issues, revert affected files and keep callback APIs unchanged.

## Artifacts and Notes

Implementation evidence and command outputs will be appended after coding.

## Interfaces and Dependencies

No new third-party dependency is introduced. Tkinter/ttk existing runtime remains the only UI dependency. Interfaces that must remain stable:

- `MainWindowView` constructor callback args.
- View public setter methods consumed by VMs/presenters.
- Existing dialog callbacks in `SettingsDialog` and `DiscoveryResultsDialog`.


Update note (2026-02-12): Completed implementation milestones and recorded validation evidence.
