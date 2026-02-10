# MVVM + Hexagonal Tutorial Notebooks

To make the architecture easier to learn hands-on, this repository includes two tutorial notebooks in `docs/`.

They are written as a guided sequence and complement the architecture/workflow docs.

## Recommended reading order

1. **`docs/mvvm_hexagonal_intro.ipynb`**  
   Introduces the core ideas behind MVVM + Hexagonal design in this project: layer boundaries, dependency direction, and why orchestration belongs in UseCases.

2. **`docs/mvvm_hexagonal_part2_view_viewmodel.ipynb`**  
   Continues with concrete View/ViewModel collaboration patterns, including command/state flow and where UI responsibilities stop.

## How to use them with the docs

- Read **[Architecture Overview](architecture_overview.md)** first for the compact system map.
- Then work through the notebooks in order for a guided walkthrough.
- Afterwards, jump to:
  - **[SEVA GUI Workflows](workflows_seva.md)** for end-to-end GUI flows
  - **[REST API Workflows](workflows_rest_api.md)** for the server-side lifecycle

## Notes for contributors

When architecture behavior changes (for example, where validation lives or how UseCases orchestrate status polling), keep the notebooks aligned with:

- `docs/architecture_overview.md`
- `docs/workflows_seva.md`
- `docs/workflows_rest_api.md`

This keeps the conceptual tutorial and implementation docs consistent.
