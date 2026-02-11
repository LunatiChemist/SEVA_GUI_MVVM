# Contributing

Thanks for contributing to SEVA. This guide summarizes how to work on the
repository and keep changes aligned with the MVVM + Hexagonal architecture.

## Workflow

1. Create a feature branch from `main`.
2. Keep PRs small and focused.
3. Update docs when behavior changes.

## Architecture guardrails

- **Views**: UI/rendering only. No I/O, no domain rules, no mapping.
- **ViewModels**: UI state + commands only. No network/filesystem I/O.
- **UseCases**: Orchestrate workflows and call ports.
- **Adapters**: Implement ports for I/O (HTTP, filesystem, discovery).
- **Domain types**: Use domain objects above adapters (no raw dict/JSON).

## Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the GUI:

```bash
python -m seva.app.main
```

Run the REST API (Linux/Raspberry Pi):

```bash
cd rest_api
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Tests

From the repo root:

```bash
pytest -q
```

## Docs

- Update `docs/` when behavior or workflow changes.
- Run `mkdocs build` before shipping doc-heavy changes.

## Documentation change checklist

For doc-heavy PRs, verify the following before submission:

- [ ] Endpoint methods/paths were re-checked against `rest_api/app.py`.
- [ ] GUI workflow steps were re-checked against `seva/app/run_flow_presenter.py` (and related use cases/adapters).
- [ ] Terminology is consistent (`run_id`, `group_id`, job, snapshot).
- [ ] `README.md` remains a lightweight hub (no duplicate deep reference content).
- [ ] Navigation entries in `mkdocs.yml` were updated for any added/renamed pages.
