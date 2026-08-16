## Summary

Describe the problem this change solves and the user-visible behavior it introduces or changes.

## Scope and compatibility

Explain any graph-schema, CLI, renderer, or proof-checker compatibility impact. State `None` if this change has no compatibility impact.

## Validation

List the commands run and their outcomes.

```text
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

## Documentation and changelog

- [ ] I updated documentation where behavior or usage changed.
- [ ] I updated `CHANGELOG.md` for user-visible changes.
- [ ] I did not add secrets, credentials, private data, or unreviewed generated artifacts.
- [ ] I added or updated tests for the changed behavior.
