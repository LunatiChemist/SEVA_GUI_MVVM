# Codex Execution Plans (ExecPlans)

This document defines the requirements for an **execution plan** (“ExecPlan”): a design document that a coding agent can follow to deliver a working feature or system change.

Treat the reader as a complete beginner to this repository: they have only the current working tree and the single ExecPlan file you provide. There is **no memory** of prior plans and **no external context**.

## How to use ExecPlans and PLANS.md

**When authoring an ExecPlan**  
Follow PLANS.md **to the letter**. If PLANS.md is not in your current context, refresh your memory by reading the entire file. Start from the skeleton near the end and flesh it out as you research.

**When implementing an ExecPlan**  
Do not ask the user for “next steps.” Proceed to the next milestone. Keep the “living sections” updated at every stopping point, splitting items as needed (done vs remaining). Resolve ambiguities autonomously and commit frequently.

**When discussing or revising an ExecPlan**  
Record decisions in the `Decision Log` so that it is always clear why the plan changed. ExecPlans are living documents: it must be possible to restart work using *only* the ExecPlan.

**When requirements are challenging or unknown**  
Use explicit prototyping/spike milestones (“toy implementations”) to validate feasibility early. Read relevant source code and dependencies as needed, and include prototypes to guide the final approach.

## Requirements

### NON‑NEGOTIABLE REQUIREMENTS

- Every ExecPlan must be **fully self‑contained**: in its current form it contains all knowledge and instructions needed for a novice to succeed.
- Every ExecPlan is a **living document**: it must be revised as progress is made, discoveries occur, and design decisions are finalized — while staying self‑contained.
- Every ExecPlan must enable a complete novice to implement the work **end‑to‑end** without prior knowledge of this repo.
- Every ExecPlan must produce **demonstrably working behavior**, not merely code changes that “match a definition.”
- Every ExecPlan must define every “term of art” (specialized jargon) in plain language — or avoid using it.

Begin with **purpose and intent**: explain why the work matters from a user’s perspective, what someone can do after the change, and how to see it working (commands + expected outputs). Then guide the reader through exact steps: what to edit, what to run, and what to observe.

The agent executing the plan can list files, read files, search, run the project, and run tests. It has no prior context. Repeat assumptions explicitly. Do not rely on external blogs or docs; if knowledge is required, embed it in the plan in your own words. If the plan builds on a prior checked‑in ExecPlan, incorporate it by reference; otherwise include all needed context.

## Formatting

ExecPlans have strict formatting rules:

- An ExecPlan delivered **in a chat message** must be **one single fenced code block** labeled `md` (triple backticks).
- Do **not** nest additional triple‑backtick blocks inside the ExecPlan.  
  When you need commands, diffs, transcripts, or code, present them as **indented blocks** inside that single fence.
- Use correct Markdown headings (`#`, `##`, …). Use two newlines after every heading. Use ordered/unordered lists with correct syntax.

When writing an ExecPlan to a Markdown file where the file content is only the ExecPlan, **omit** the outer triple backticks.

Write in plain prose. Prefer sentences over long lists. Avoid tables and long enumerations unless brevity would obscure meaning. Checklists are permitted **only** in the `Progress` section, where they are mandatory. Narrative sections should be prose‑first.

## Guidelines

Self‑containment and plain language are paramount.

- If you introduce a non‑ordinary phrase (“daemon”, “middleware”, “RPC”, etc.), define it immediately and explain how it appears in this repo (files, commands).
- Do not say “as defined previously” or “according to another doc.” Include the necessary explanation here, even if it repeats.

Avoid common failure modes:

- Do not rely on undefined jargon.
- Do not specify a feature so narrowly that the result compiles but does nothing meaningful.
- Do not outsource key decisions to the reader.
- When ambiguity exists, resolve it in the plan and explain why.

Anchor the plan in **observable outcomes**:

- State what a user can do after implementation.
- Provide commands to run and outputs to expect.
- Phrase acceptance as human‑verifiable behavior (e.g., an HTTP request that returns `200 OK` with a specific body), not internal structure (“added a struct”).

Specify repo context explicitly:

- Name files by **repository‑relative paths**.
- Name functions and modules precisely.
- When running commands, show the working directory and exact command line.
- When outcomes depend on environment, state assumptions and provide alternatives when reasonable.

Be idempotent and safe:

- Steps should be repeatable without damage or drift.
- If a step can fail halfway, describe how to retry or adapt.
- If destructive actions are needed, describe backups or safe fallbacks.
- Prefer additive, testable changes followed by deletions that keep tests passing.

Validation is mandatory:

- Include instructions to run tests and/or start the system.
- Provide expected outputs and common error messages so novices can distinguish success from failure.
- Where possible, include an end‑to‑end scenario (CLI invocation, HTTP transcript, etc.).

Capture evidence:

- Include concise terminal output, small diffs, or logs as **indented examples**.
- Keep evidence focused on what proves success.

## Milestones

Milestones are narrative, not bureaucracy.

For each milestone, write a short paragraph describing:
- the scope and goal,
- what will exist at the end that did not exist before,
- the commands to run,
- and the acceptance you expect to observe.

Milestones must be independently verifiable and incrementally advance the overall plan.

Progress and milestones are different:
- **Milestones** tell the story (goal → work → result → proof).
- **Progress** tracks granular tasks and must reflect the true state at every stopping point.

## Living plans and design decisions

ExecPlans must include and maintain these sections (not optional):

- `Progress`
- `Surprises & Discoveries`
- `Decision Log`
- `Outcomes & Retrospective`

Rules:

- As key design decisions are made, update the plan and record them in `Decision Log`.
- When you encounter unexpected behavior, performance tradeoffs, bugs, or semantics that shape the approach, record them in `Surprises & Discoveries` with concise evidence.
- If you change course mid‑implementation, document why in `Decision Log` and reflect it in `Progress`.
- At completion (or major milestones), write an `Outcomes & Retrospective` entry summarizing what was achieved, what remains, and lessons learned.

When revising a plan, ensure changes are reflected across all sections, including living sections, and add a short note at the bottom describing what changed and why.

## Prototyping milestones and parallel implementations

Prototyping milestones are allowed and often encouraged when they de‑risk a larger change.

- Clearly label a milestone as “Prototyping.”
- Describe how to run and observe results.
- Define criteria for promoting or discarding the prototype.

Prefer additive code changes first, then deletions that keep tests passing.

Parallel implementations (e.g., a new adapter alongside an older path during migration) are acceptable when they reduce risk, but they must be explicitly temporary:

- Describe how to validate both paths.
- Describe exactly how and when the legacy path will be removed.

## Skeleton of a good ExecPlan

    # <Short, action‑oriented description>

    This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

    If PLANS.md is checked into the repo, reference the path to that file here from the repository root and note that this document must be maintained in accordance with PLANS.md.

    ## Purpose / Big Picture

    Explain in a few sentences what someone gains after this change and how they can see it working. State the user‑visible behavior you will enable.

    ## Progress

    Use a list with checkboxes to summarize granular steps. Every stopping point must be documented here, even if it requires splitting a partially completed task into two (“done” vs “remaining”). This section must always reflect the actual current state of the work.

    - [x] (2026-01-26 10:00Z) Example completed step.
    - [ ] Example incomplete step.
    - [ ] Example partially completed step (completed: X; remaining: Y).

    Use timestamps to measure rates of progress.

    ## Surprises & Discoveries

    Document unexpected behaviors, bugs, optimizations, or insights discovered during implementation. Provide concise evidence.

    - Observation: …
      Evidence: …

    ## Decision Log

    Record every decision made while working on the plan:

    - Decision: …
      Rationale: …
      Date/Author: …

    ## Outcomes & Retrospective

    Summarize outcomes, gaps, and lessons learned at major milestones or at completion. Compare the result against the original purpose.

    ## Context and Orientation

    Describe the current state relevant to this task as if the reader knows nothing. Name the key files and modules by full path. Define any non‑obvious term you will use. Do not refer to prior plans.

    ## Plan of Work

    Describe, in prose, the sequence of edits and additions. For each edit, name the file and location (function, module) and what to insert or change. Keep it concrete and minimal.

    ## Concrete Steps

    State the exact commands to run and where to run them (working directory). When a command generates output, show a short expected transcript so the reader can compare. Update this section as work proceeds.

    ## Validation and Acceptance

    Describe how to start or exercise the system and what to observe. Phrase acceptance as behavior, with specific inputs and outputs. If tests are involved, say: “run <project test command> and expect <N> passed; the new test <name> fails before the change and passes after.”

    ## Idempotence and Recovery

    If steps can be repeated safely, say so. If a step is risky, provide a safe retry or rollback path. Keep the environment clean after completion.

    ## Artifacts and Notes

    Include the most important transcripts, diffs, or snippets as indented examples. Keep them concise and focused on what proves success.

    ## Interfaces and Dependencies

    Be prescriptive. Name the libraries, modules, and services to use and why. Specify the types/interfaces and function signatures that must exist at the end.

---

If this guidance is followed, a single stateless agent — or a human novice — can read an ExecPlan top to bottom and produce a working, observable result. That is the bar: **SELF‑CONTAINED, NOVICE‑GUIDING, OUTCOME‑FOCUSED.**
