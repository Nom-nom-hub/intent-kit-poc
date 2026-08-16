# Intent Contract

**Project:** Intent Kit
**Graph updated:** 2026-08-16T21:49:21+00:00

## Outcomes

- **OUT-001 — Sustain a trustworthy local-first Intent Kit release** (`active`): Intent Kit must demonstrate that its own repository can carry explicit intent, reviewable evidence, and reliable release practices.

## Requirements

- **REQ-001 — Publish governed, licensed source** (`active`): The repository must include a recognized license and public contribution and security policies. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-002 — Preserve reliable Spec Kit migration** (`active`): The repository must document and ship a read-only importer with source provenance for completed Spec Kit feature artifacts. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-003 — Require a reproducible local quality gate** (`active`): Every repository update must pass linting, formatting, tests, package build, and an installed-command smoke test before it is pushed. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-004 — Make change impact visible** (`active`): Users must be able to identify source drift, connected graph records, and proof gaps before accepting a specification or implementation change. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-005 — Enforce public continuous integration** (`active`): Every main-branch and pull-request change must run the project quality gate on supported Python versions and build a smoke-tested distribution. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-006 — Apply risk-calibrated policies** (`active`): Intent Kit must make risk, proof, freshness, and review expectations explicit through local Policy Packs. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).
- **REQ-007 — Authorize controlled external proof checks** (`active`): Intent Kit must execute external proof automation only when a project allowlist pins its identity, manifest, and entrypoint. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
