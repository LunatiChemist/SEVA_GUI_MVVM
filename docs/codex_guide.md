# ChatGPT Codex User Guide (SEVA GUI MVVM)

This document is a formal guide for developers who want to use ChatGPT Codex effectively in this repository.

It focuses on practical collaboration: selecting the correct repository context, planning work, implementing safely, validating changes, and iterating through pull requests.

## 1. Repository Context and Governing Documents

### 1.1 Read `AGENTS.md` first (required)

Before requesting code changes, read `AGENTS.md` once to understand repository guardrails. It already covers:

- MVVM + Hexagonal layer boundaries,
- domain objects vs. raw dict/JSON above adapters,
- error propagation policy,
- avoidance of legacy fallback paths,
- testing direction.

Because this is already documented centrally, you do not need to restate all architecture boundaries in every prompt.

### 1.2 Use `.agent/PLANS.md` when needed (optional, situation-dependent)

Reading `.agent/PLANS.md` is optional for small or straightforward work.

Use it when work is large, cross-cutting, risky, or unclear (for example major refactors, architecture-impacting features, or complex migrations).

### 1.3 Update guardrails over time (recommended)

It can be useful to refine `AGENTS.md` as team understanding evolves, for example:

- before a large refactor,
- after long periods without updates,
- when recurring review issues appear.

## 2. Quickstart Workflow (Web)

Use this operational flow when working with Codex in the web interface.

1. Select repository and target branch.
2. Ask your implementation or analysis question.
3. Review generated plan and code changes.
4. Let Codex create a pull request.
5. Test the branch independently.
6. Decide next action:
   - merge branch,
   - make additional manual commits,
   - or continue improving with Codex and update the branch.

This workflow should be your default working model.

## 3. Prompting Standard: Required vs Optional Inputs

Use this structure to communicate with Codex.

### 3.1 Required

- **Goal/outcome**: what should work after the change?
- **Scope/context**: which files, modules, or user flows are relevant?
- **Constraints/non-goals**: what must remain unchanged?

### 3.2 Optional but helpful

- touched files to prioritize,
- risk points to watch,
- validation strategy expectations,
- requirement that Codex asks clarifying questions before implementation.

Recommended instruction to include when requirements are unclear:

- “Before implementing, ask clarifying questions until ambiguity is low.”

## 4. Practical Task Workflows

### 4.1 Bugfix Workflow

Start from evidence first:

- provide a GUI screenshot,
- provide a terminal screenshot,
- or paste direct terminal output.

Then work iteratively with Codex:

- ask where Codex thinks the issue originates,
- request likely root causes and candidate fixes,
- if you already have hypotheses, provide them and refine direction together.

Important practice note:

- Codex can sometimes produce symptom-level fixes (“band-aid fixes”).
- Ask explicitly for a deep/root-cause fix when needed.
- Final confidence still comes from testing and code familiarity.

This pattern often works very well for smaller fixes.

### 4.2 Refactor Workflow

For refactors, planning iterations are critical.

Recommended approach:

- run multiple plan-review cycles before coding,
- ask Codex to ask questions and challenge assumptions,
- for larger refactors, optionally reference `.agent/PLANS.md`,
- update affected documentation in `docs/` when behavior, workflows, or interfaces change.

Important experience-based guidance:

- Codex may introduce unnecessary fallback paths.
- Codex may re-implement helpers that already exist.

To reduce this risk, instruct explicitly:

- “Scan the relevant codebase deeply before proposing refactor steps.”
- “Search for existing helpers/utilities before creating new ones.”
- “Do not introduce fallback branches unless explicitly required.”

### 4.3 Feature Implementation Workflow

Feature work can start in two valid modes:

- **exploratory mode**: requirements are still vague,
- **specified mode**: architecture and expected flow are already known.

If requirements are vague, use planning iterations to converge:

- start broad,
- refine design through questions/answers,
- then implement once direction is stable.

If requirements are clear, provide explicit implementation guidance (layer ownership, contracts, validation).

For feature work, keep documentation in `docs/` up to date whenever user-facing behavior, workflows, setup steps, or interfaces are changed.

Global simplicity rule for feature work and refactors:

- apply **YAGNI** (*You Aren't Gonna Need It*: avoid building speculative functionality),
- apply **KISS** (*Keep It Simple, Stupid*: prefer the simplest solution that satisfies current requirements),
- apply **DRY** (*Don't Repeat Yourself*: reuse existing logic instead of duplicating behavior),
- ask Codex to review a broad file set during planning to avoid local optimization and overengineering.

## 5. Common Failure Modes in Practice

Watch for these recurring issues:

- implementing too quickly without clarifying uncertainty,
- solving symptoms instead of root causes,
- duplicating existing helpers/utilities,
- adding unnecessary fallback/legacy logic,
- overengineering simple requirements,
- validating too little before merge.

When one of these appears, return to planning and request targeted clarification.

## 6. How to Steer Codex During Planning Iterations

Use concise steering instructions such as:

- “Propose an initial plan and list open questions first.”
- “Identify uncertainties and ask me what you need before coding.”
- “Review more files before finalizing architecture decisions.”
- “Prefer existing helpers over new abstractions when possible.”
- “Prioritize a deep fix over a temporary symptom patch.”
- “Keep solution simple (YAGNI/KISS/DRY), avoid overengineering.”

A short, explicit steering message is usually enough to improve output quality significantly.

## 7. Decision Checklist Before Merge

Before merging a Codex-generated branch, confirm:

- [ ] behavior is correct in your own branch testing,
- [ ] no obvious fallback/legacy detours were introduced,
- [ ] existing helpers were reused where appropriate,
- [ ] complexity is justified and not overengineered,
- [ ] follow-up improvements are documented if needed.

If these checks fail, iterate on the same branch with Codex or make targeted manual commits before merge.
