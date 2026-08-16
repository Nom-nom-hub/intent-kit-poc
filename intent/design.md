# Design and Decision Record

**Project:** Intent Kit

## Active Requirements

- **REQ-001 — Publish governed, licensed source** (`active`): The repository must include a recognized license and public contribution and security policies.
- **REQ-002 — Preserve reliable Spec Kit migration** (`active`): The repository must document and ship a read-only importer with source provenance for completed Spec Kit feature artifacts.
- **REQ-003 — Require a reproducible local quality gate** (`active`): Every repository update must pass linting, formatting, tests, package build, and an installed-command smoke test before it is pushed.
- **REQ-004 — Make change impact visible** (`active`): Users must be able to identify source drift, connected graph records, and proof gaps before accepting a specification or implementation change.
- **REQ-005 — Enforce public continuous integration** (`active`): Every main-branch and pull-request change must run the project quality gate on supported Python versions and build a smoke-tested distribution.
- **REQ-006 — Apply risk-calibrated policies** (`active`): Intent Kit must make risk, proof, freshness, and review expectations explicit through local Policy Packs.
- **REQ-007 — Authorize controlled external proof checks** (`active`): Intent Kit must execute external proof automation only when a project allowlist pins its identity, manifest, and entrypoint.
- **REQ-008 — Provide a controlled Agent Computer** (`active`): Agents must inspect and operate an Intent Kit project through a project-scoped JSON protocol, bounded workspace, explicit apply mode, approved proof checks, and auditable actions rather than unrestricted shell access.

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

### DEC-006 — Keep policies declarative and local

**Status:** `proposed`
**Rationale:** JSON-only packs provide consistent defaults without executing code or weakening the trusted checker boundary.
**Addresses:** REQ-006 — Apply risk-calibrated policies
**Alternatives considered:** Embed policy behavior in hard-coded workflow prompts

### DEC-007 — Use manifest-pinned JSON subprocesses

**Status:** `proposed`
**Rationale:** Explicit project authorization and digest pinning make external execution reviewable while preserving graph ownership in the core.
**Addresses:** REQ-007 — Authorize controlled external proof checks
**Alternatives considered:** Discover installed Python checker packages automatically

### DEC-008 — Use a project-scoped Agent Computer protocol

**Status:** `proposed`
**Rationale:** A narrow JSON protocol keeps graph mutation, policy resolution, proof execution, and evidence persistence inside Intent Kit while giving agents useful local work capabilities.
**Addresses:** REQ-008 — Provide a controlled Agent Computer
**Alternatives considered:** Grant agents unrestricted shell access to the project, Expose the graph JSON directly for agents to edit

## Implementation Tasks

No implementation tasks have been imported or recorded yet.

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
