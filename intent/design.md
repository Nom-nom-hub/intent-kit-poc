# Design and Decision Record

**Project:** Intent Kit

## Active Requirements

- **REQ-001 — Publish governed, licensed source** (`active`): The repository must include a recognized license and public contribution and security policies.
- **REQ-002 — Preserve reliable Spec Kit migration** (`active`): The repository must document and ship a read-only importer with source provenance for completed Spec Kit feature artifacts.
- **REQ-003 — Require a reproducible local quality gate** (`active`): Every repository update must pass linting, formatting, tests, package build, and an installed-command smoke test before it is pushed.
- **REQ-004 — Make change impact visible** (`active`): Users must be able to identify source drift, connected graph records, and proof gaps before accepting a specification or implementation change.
- **REQ-005 — Enforce public continuous integration** (`active`): Every main-branch and pull-request change must run the project quality gate on supported Python versions and build a smoke-tested distribution.

## Decisions

### DEC-001 — Keep repository governance version-controlled

**Status:** `proposed`
**Rationale:** Version-controlled policies make the public maintenance contract reviewable and auditable.
**Addresses:** REQ-001 — Publish governed, licensed source
**Alternatives considered:** Maintain governance only in external documentation

### DEC-002 — Import source artifacts read-only with provenance

**Status:** `proposed`
**Rationale:** Read-only import plus artifact hashes preserves trust in the migration record.
**Addresses:** REQ-002 — Preserve reliable Spec Kit migration
**Alternatives considered:** Rewrite source Markdown during import

### DEC-003 — Record release evidence in the intent graph

**Status:** `proposed`
**Rationale:** A durable evidence record keeps release verification reviewable alongside requirements.
**Addresses:** REQ-003 — Require a reproducible local quality gate
**Alternatives considered:** Rely only on terminal history

### DEC-004 — Use deterministic bidirectional graph traversal

**Status:** `proposed`
**Rationale:** Traversing typed edges in both directions exposes outcome context, implementation tasks, proof obligations, and evidence without inferring semantic changes.
**Addresses:** REQ-004 — Make change impact visible
**Alternatives considered:** Show only downstream implementation tasks

### DEC-005 — Run a minimal GitHub Actions quality matrix

**Status:** `proposed`
**Rationale:** A public, repeatable quality matrix makes validation visible to contributors and catches regressions before merge.
**Addresses:** REQ-005 — Enforce public continuous integration
**Alternatives considered:** Rely only on local validation before push

## Implementation Tasks

No implementation tasks have been imported or recorded yet.

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
