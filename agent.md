# SEVA MVVM Pro — Refactor Guide (Phase A → D)

> **Scope:** This replaces the previous Phase-2 agent guide.  
> Defines non-negotiable architectural rules, contracts, and quality gates so Codex delivers cohesive increments.  
> **Current focus:** **Phase A – Domain Kernel (Value Objects, Entities, Snapshot Normalizer).**  
> Later phases (B–E) are contextual; **Phase B (RunFlowCoordinator)** and **Phase E (Discovery)** require design reviews before implementation.

---

## Roles

| Role | Responsibility |
|------|----------------|
| **Pro (Product/Architect)** | Sets priorities, approves designs & merges. |
| **Codex (Implementer)** | Delivers small, testable PRs strictly following this guide. |
| **Maintainer** | Branching, CI, release hygiene. |

---

## Architecture Principles (Invariants)

### MVVM + Hexagon (unchanged)
- **Views (Tkinter)** = UI-only — no HTTP, no domain logic, no mapping.  
- **ViewModels** = State + Commands, no I/O.  
- **UseCases** = Orchestration (start / validate / poll / cancel / download / layouts / test).  
- **Adapters** = pure port implementations (REST / Storage); no orchestration inside adapters.

### Phase-Level Commitments
- **One job per well** (no signature grouping).  
- **Server-driven progress** is the single source of truth (status / progress_pct / remaining_s / timestamps). No client math.  
- **No fallbacks / legacy branches.** When a path is replaced, the old one is deleted.  
- **Settings & Layouts = JSON only** (flat keys; no nested legacy).  
- **Plan** carries `experiment`, optional `subdir`, `client_datetime`; server builds run paths.

### Refactor Guardrails (new)
- **Domain types only** across UseCases.  
  - Input = `ExperimentPlan`, Output = `GroupSnapshot`.  
  - No raw dicts in UseCases.  
- **Single validation path:** Client does pre-checks (selection / required fields), server validates modes.  
- **Unified error policy:** Adapters raise typed errors; UseCases map logical errors; Views toast – no double wrapping.

## Quality Gates

- No raw dicts in UseCases.  
- No UI logic outside Views/VMs.  
- No client progress math.  
- No legacy/fallbacks after merge.  
- Docstrings for each class/method (1–2 lines + key steps).  