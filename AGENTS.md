# AGENTS.md

This file contains working agreements (guardrails) for coding agents (e.g., Codex) operating in this repository.

## Non‑negotiable guardrails

### Architecture boundaries (MVVM + Hexagonal)

- **Views**: UI/rendering only. No I/O, no domain rules, no mapping, no error swallowing.
- **ViewModels**: UI state + commands only. No network/filesystem I/O, no API payload construction.
- **UseCases**: Orchestration and workflow (e.g., start/validate/poll/cancel/download). Business flow lives here.
- **Adapters**: Implement ports (HTTP, filesystem, NAS, DB, vendor libs). No orchestration.

### Domain types over raw dict/JSON

- Above the adapter boundary, use **domain objects** (or explicit DTOs) — **never** pass raw `dict`/JSON through Views/VMs/UseCases.
- Normalize and validate **early**, close to the contract boundary, not late in UI layers.

### Server status is the source of truth

- Do not invent client-side progress or derived status when the server provides authoritative state.

### Unified error policy (no swallowing)

- Adapters throw **typed errors**.
- UseCases map/contextualize errors into a consistent domain/app error model (including user-facing codes/messages where applicable).
- Views/VMs display or propagate; they do **not** swallow exceptions.

### No legacy / no fallbacks

- When a path is replaced, **delete the old path**. Avoid “just in case” branches.

### Centralize mode/token handling

- A single “Mode Registry” module should own: normalization, token mapping, validation, and UI labels.

### Testing approach

- Prefer **contract-driven tests** at the UseCase↔Adapter boundary.
- Keep UI tests minimal; UI should remain “dumb”.

### Reproducible dependencies

- If a dependency is pulled via Git URL or otherwise non-reproducible offline, document and support a vendor/offline workflow.

---

## ExecPlans

When writing complex features or significant refactors, use an **ExecPlan** (as described in `.agent/PLANS.md`) from design to implementation.

An ExecPlan is required when the work:
- touches multiple layers/files in a coordinated way,
- requires architecture decisions (ports/contracts/data models),
- involves migration/legacy removal risk,
- or has meaningful unknowns that benefit from prototypes/spikes.

Use the ExecPlan as a **living document**: keep progress, discoveries, and decisions up to date while implementing.
