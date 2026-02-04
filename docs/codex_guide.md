# ChatGPT Codex Guide

This guide shows how to use ChatGPT Codex effectively on this repository. It is
aimed at Python developers who are new to the codebase and want reliable,
architecture-safe changes.

## Architecture guardrails to mention in prompts

- **Views**: UI/rendering only. No I/O, no domain rules, no mapping.
- **ViewModels**: UI state + commands only. No network/filesystem I/O.
- **UseCases**: Orchestrate workflows, call ports.
- **Adapters**: Implement ports for I/O (HTTP, filesystem, discovery).
- **Domain types**: Use domain objects instead of raw dict/JSON above adapters.

These rules help Codex avoid putting logic in the wrong layer.

## Prompting checklist

Before asking for code changes, include:

1. **Goal** (what you want to change).
2. **Scope** (which folders/files are relevant).
3. **Architecture rules** (MVVM + Hexagonal boundaries above).
4. **Constraints**:
   - Avoid defensive programming for unlikely scenarios.
   - Avoid KISS/YAGNI/DRY slogans as substitutes for reasoning.
   - Provide a plan before coding.
   - Prefer minimal, explicit changes with clear call chains.

## Suggested prompt template

```
Goal:
  Add/modify <feature> in the SEVA GUI.

Scope:
  - Relevant areas: seva/app/*, seva/viewmodels/*, seva/usecases/*, seva/adapters/*
  - Ignore UI end-user docs.

Architecture rules:
  - Views are UI-only, no I/O.
  - ViewModels are state/commands only, no network/filesystem I/O.
  - UseCases orchestrate workflows and call ports.
  - Adapters implement ports for I/O.
  - Use domain objects above adapters.

Constraints:
  - Avoid defensive coding for unlikely paths.
  - No KISS/YAGNI/DRY slogans; explain tradeoffs instead.
  - Produce a plan first, then implement.

Context:
  - Link: docs/architecture_overview.md
  - Link: docs/workflows_seva.md
  - Link: docs/classes_seva.md
```

## Example prompt

```
Goal:
  Add a new "Export Summary" action that saves a CSV from the run overview.

Scope:
  - GUI: seva/app/views/run_overview_view.py
  - ViewModel: seva/viewmodels/runs_vm.py
  - UseCase: seva/usecases/export_summary.py
  - Adapter: seva/adapters/storage_local.py

Architecture rules:
  - Views are UI-only, no I/O.
  - ViewModels are state/commands only, no network/filesystem I/O.
  - UseCases orchestrate workflows and call ports.
  - Adapters implement ports for I/O.
  - Use domain objects above adapters.

Constraints:
  - Avoid defensive coding for unlikely paths.
  - No KISS/YAGNI/DRY slogans; explain tradeoffs instead.
  - Produce a plan first, then implement.
```
