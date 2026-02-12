# SEVA Developer Documentation

Welcome to the SEVA documentation.

This documentation is intended for developers working on the SEVA GUI
(MVVM architecture) and the associated REST API.

> Docs track the `main` branch unless otherwise noted.

## Motivation

SEVA was created because the previous GUI was difficult to extend and even
harder to migrate when device communication changed. Once control moved to
network-based pyBEEP integration, the UI needed to work reliably with a REST
API boundary, but the old structure mixed concerns too much to support that
shift cleanly.

The core goal of this project is pragmatic maintainability: new features should
be added without rewriting unrelated UI code, and infrastructure changes should
not force architecture-wide refactors. MVVM + Hexagonal boundaries make that
possible by keeping Views and ViewModels focused on UI state, moving workflow
orchestration into UseCases, and isolating all external I/O in adapters.

This also improves diversification and long-term evolution. Through ports and
adapters, transport/back-end integrations can be swapped more safely (for
example REST-based integration vs. legacy AMETEK-style paths) while preserving
GUI workflows. In run execution, server-reported state remains the single source
of truth for status/progress, which avoids fragile client-side assumptions and
keeps behavior testable at the use-case boundary.

## Start here

If you are new to the project, follow this order:

1. Read **What is this repo?** (below) to understand the scope.
2. Set up your environment in **[Development Setup](dev-setup.md)**.
3. If you use the browser client, follow **[Web UI Setup](web-ui-setup.md)**.
4. Configure/deploy the API with **[REST API Setup Tutorial](rest-api-setup.md)**.
5. Review the **[Architecture Overview](architecture_overview.md)** to learn the MVVM + Hexagonal boundaries.
6. Work through the **[MVVM + Hexagonal Tutorial Notebooks](mvvm_tutorial_notebooks.md)** for a guided architecture walkthrough.
7. Explore the **[SEVA GUI workflows](workflows_seva.md)** and **[REST API workflows](workflows_rest_api.md)**.
8. Use **[Troubleshooting](troubleshooting.md)** and the **[Glossary](glossary.md)** when you get stuck.
9. Review the **[ChatGPT Codex Guide](codex_guide.md)** for AI-assisted changes.

## Quick path chooser

Use this if you want the shortest path to a specific task:

- **I want to run GUI/API locally** -> [Development Setup](dev-setup.md), then [REST API Setup Tutorial](rest-api-setup.md).
- **I want to run the browser client** -> [Web UI Setup](web-ui-setup.md).
- **I want to understand architecture boundaries** -> [Architecture Overview](architecture_overview.md).
- **I need call-chain debugging for start/poll/cancel** -> [SEVA GUI Workflows](workflows_seva.md) and [REST API Workflows](workflows_rest_api.md).
- **I need endpoint/module reference details** -> [REST API Classes & Modules](classes_rest_api.md) and [SEVA GUI Classes & Modules](classes_seva.md).
- **I need end-user GUI operation help** -> [GUI Overview & How to Use](gui_overview_how_to_use.md).

### What is this repo?

This repository contains the SEVA GUI (MVVM + Hexagonal architecture) and the
associated REST API service. The Tkinter GUI lives in `seva/`, the Web UI lives
in `web_ui/`, and the REST API lives in `rest_api/`.

### How to run GUI locally (Windows/Linux)

Follow the steps in **[Development Setup](dev-setup.md)** to configure Python and start the GUI.

### How to run REST API locally (Linux/Raspberry Pi)

See **[REST API Setup Tutorial](rest-api-setup.md)** for the complete Linux/Raspberry Pi setup,
including install, verification, and restart steps.

### How to run the Web UI locally (desktop browser)

See **[Web UI Setup](web-ui-setup.md)** for install, run, build, and deployment path details.

### Where to change what? (View vs ViewModel vs UseCase)

Use this quick guide when deciding where a change should live:

- **Views** (`seva/app/views/*`): UI rendering only.
- **ViewModels** (`seva/viewmodels/*`): UI state + commands.
- **UseCases** (`seva/usecases/*`): Orchestration and workflows.
- **Adapters** (`seva/adapters/*`): External I/O (HTTP, filesystem, discovery).

## Scope

This documentation set contains two tracks:

- **Developer docs** (architecture, setup, workflows, module responsibilities)
- **User guide docs** (GUI operation walkthroughs)

The primary focus remains developer-oriented material for contributors working
inside `seva/` and `rest_api/`.

## Documentation map

### Developer track

Follow this order for a linear tour through the docs:

1. **[Development Setup](dev-setup.md)** (local environment + run GUI/API)
2. **[Web UI Setup](web-ui-setup.md)** (browser client install/run/build)
3. **[REST API Setup Tutorial](rest-api-setup.md)** (API install, env, smoke tests, restart)
4. **[Architecture Overview](architecture_overview.md)** (MVVM + Hexagonal boundaries)
5. **[MVVM + Hexagonal Tutorial Notebooks](mvvm_tutorial_notebooks.md)**
6. **[SEVA GUI workflows](workflows_seva.md)**
7. **[REST API workflows](workflows_rest_api.md)**
8. **[Troubleshooting](troubleshooting.md)**
9. **[Glossary](glossary.md)**
10. **[ChatGPT Codex Guide](codex_guide.md)**

### User guide track

- **[GUI Overview & How to Use](gui_overview_how_to_use.md)**
