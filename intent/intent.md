# Intent Contract

**Project:** Intent Kit
**Graph updated:** 2026-08-16T22:28:27+00:00

## Outcomes

- **OUT-001 — Sustain a trustworthy local-first Intent Kit release** (`active`): Intent Kit must demonstrate that its own repository can carry explicit intent, reviewable evidence, and reliable release practices.
- **OUT-002 — Imported Spec Kit feature: Reviewed Import Refresh** (`active`): User description: "Refresh imported specifications through an explicit reviewed delta.

## Requirements

- **REQ-001 — Publish governed, licensed source** (`active`): The repository must include a recognized license and public contribution and security policies. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-002 — Preserve reliable Spec Kit migration** (`active`): The repository must document and ship a read-only importer with source provenance for completed Spec Kit feature artifacts. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-003 — Require a reproducible local quality gate** (`active`): Every repository update must pass linting, formatting, tests, package build, and an installed-command smoke test before it is pushed. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-004 — Make change impact visible** (`active`): Users must be able to identify source drift, connected graph records, and proof gaps before accepting a specification or implementation change. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-005 — Enforce public continuous integration** (`active`): Every main-branch and pull-request change must run the project quality gate on supported Python versions and build a smoke-tested distribution. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release.
- **REQ-006 — Apply risk-calibrated policies** (`active`): Intent Kit must make risk, proof, freshness, and review expectations explicit through local Policy Packs. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).
- **REQ-007 — Authorize controlled external proof checks** (`active`): Intent Kit must execute external proof automation only when a project allowlist pins its identity, manifest, and entrypoint. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).
- **REQ-008 — Provide a controlled Agent Computer** (`active`): Agents must inspect and operate an Intent Kit project through a project-scoped JSON protocol, bounded workspace, explicit apply mode, approved proof checks, and auditable actions rather than unrestricted shell access. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).
- **REQ-009 — P1 user story: Review an imported specification change** (`active`): A delivery lead can inspect a proposed import delta before an Intent Kit graph is changed. Derived from: OUT-002 — Imported Spec Kit feature: Reviewed Import Refresh.
- **REQ-010 — FR-001: System MUST generate a deterministic source-and-graph delta before refr…** (`active`): System MUST generate a deterministic source-and-graph delta before refreshing imported records. Derived from: OUT-002 — Imported Spec Kit feature: Reviewed Import Refresh.
- **REQ-011 — FR-002: System MUST preserve stable graph identifiers and locally maintained po…** (`active`): System MUST preserve stable graph identifiers and locally maintained policy metadata for matching source records after an approved refresh. Derived from: OUT-002 — Imported Spec Kit feature: Reviewed Import Refresh.
- **REQ-012 — FR-003: System MUST record source digests, impact context, proof gaps, and expl…** (`active`): System MUST record source digests, impact context, proof gaps, and explicit apply requirements in every synchronization proposal. Derived from: OUT-002 — Imported Spec Kit feature: Reviewed Import Refresh.
- **REQ-013 — Synchronize imported Specs through review** (`active`): Imported Spec Kit artifacts must change through a deterministic reviewed proposal with explicit approval and stale-plan rejection. Derived from: OUT-001 — Sustain a trustworthy local-first Intent Kit release. Policy: `release-critical` (risk `R3`).

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
