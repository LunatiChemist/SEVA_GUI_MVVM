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
3. Review the **[Architecture Overview](architecture_overview.md)** to learn the MVVM + Hexagonal boundaries.
4. Explore the **[SEVA GUI workflows](workflows_seva.md)** and **[REST API workflows](workflows_rest_api.md)**.
5. Use **[Troubleshooting](troubleshooting.md)** and the **[Glossary](glossary.md)** when you get stuck.
6. Review the **[ChatGPT Codex Guide](codex_guide.md)** for AI-assisted changes.

### What is this repo?

This repository contains the SEVA GUI (MVVM + Hexagonal architecture) and the
associated REST API service. The GUI lives in `seva/`, and the REST API lives
in `rest_api/`.

### How to run GUI locally (Windows/Linux)

Follow the steps in **[Development Setup](dev-setup.md)** to configure Python and start the GUI.

### How to run REST API locally (Linux/Raspberry Pi)

See **[Development Setup](dev-setup.md)** for Linux/Raspberry Pi-specific instructions
for the FastAPI service.

### Where to change what? (View vs ViewModel vs UseCase)

Use this quick guide when deciding where a change should live:

- **Views** (`seva/app/views/*`): UI rendering only.
- **ViewModels** (`seva/viewmodels/*`): UI state + commands.
- **UseCases** (`seva/usecases/*`): Orchestration and workflows.
- **Adapters** (`seva/adapters/*`): External I/O (HTTP, filesystem, discovery).

## Scope

This documentation focuses on:

- application architecture
- workflows and control flow
- responsibilities of major modules

It does **not** document UI usage for end users.

## Documentation map

Follow this order for a linear tour through the docs:

1. **[Development Setup](dev-setup.md)** (local environment + run GUI/API)
2. **[Architecture Overview](architecture_overview.md)** (MVVM + Hexagonal boundaries)
3. **[SEVA GUI workflows](workflows_seva.md)**
4. **[REST API workflows](workflows_rest_api.md)**
5. **[Troubleshooting](troubleshooting.md)**
6. **[Glossary](glossary.md)**
7. **[ChatGPT Codex Guide](codex_guide.md)**
