# Contributing to Intent Kit

Thank you for considering a contribution to Intent Kit. The project is an **experimental, local-first proof of concept** for Intent Graph Development. Contributions should preserve the core principles of stable graph objects, explicit traceability, Git-friendly persistence, and proof-backed engineering.

## Before You Start

Please search existing issues and pull requests before opening new work. For material design changes, open an issue first so that maintainers and contributors can align on the problem, scope, and compatibility implications.

The public extension contract is documented in [`docs/custom-proof-checkers.md`](docs/custom-proof-checkers.md). New proof-checker implementations must return structured observations; only the Intent Kit core runner may persist graph evidence or change proof state.

## Local Setup

Intent Kit supports Python 3.11 and 3.12. Create an isolated environment, install development dependencies, and run the quality checks from the repository root.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.

## Contribution Requirements

Every pull request should have a narrow purpose, include tests for behavior changes, keep documentation accurate, and pass the project release quality gate. Update [`CHANGELOG.md`](CHANGELOG.md) for user-visible changes.

Do not commit secrets, credentials, environment dumps, generated caches, or private production data. Avoid adding network access, process execution, dynamic plug-in loading, or new graph relation types without an explicit design discussion.

## Pull Request Process

Use the pull request template, explain the problem and intended behavior, and provide a reproducible validation note. Maintainers may request follow-up changes, require a compatibility migration plan, or defer work that expands the POC beyond its documented scope.

By contributing, you agree that your contributions are licensed under the repository’s [MIT License](LICENSE).
