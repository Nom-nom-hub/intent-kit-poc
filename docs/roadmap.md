# Intent Kit Delivery Roadmap

Intent Kit should develop in the order that turns its typed graph into a durable user advantage while preserving its local-first, command-driven simplicity. This roadmap separates **operational reliability** from **product capability** and gives every milestone a concrete acceptance gate, a dogfood requirement, and a release boundary.

> **Operating principle:** no new capability is considered complete until it is documented, covered by tests, exercised against Intent Kit’s own graph where relevant, and validated through the project release quality gate.

## Priority Order

| Priority | Milestone | Primary user value | Release target | Dependency |
|---|---|---|---|---|
| P0 | Restore GitHub Actions CI | Every public change receives a repeatable quality gate. | Operational patch | GitHub workflow-write permission |
| P1 | Graph Insight | Users can answer what changed, what is affected, and what must be revalidated. | `v0.3.0` | Current graph, import provenance, and traceability edges |
| P2 | Policy Packs | **Delivered on `main`**: teams apply local, version-controlled risk defaults with short commands and graph-visible metadata. | `v0.4.0` candidate | Graph Insight proof-gap model |
| P3 | Controlled Checker Extensibility | **Delivered on `main`**: trusted teams add manifest-pinned local proof automation without package discovery or silent execution. | `v0.5.0` candidate | Policy packs and security model |
| P4 | Agent Computer Foundation | **Delivered on `main`**: agents use a project-scoped JSON protocol, bounded workspace, named quality commands, explicit apply mode, and audit records. | `v0.6.0` candidate | Graph, policy, proof, checker, and CI foundations |
| P5 | Incremental Spec Kit Synchronization | **Delivered on `main`**: imported features refresh through deterministic, impact-aware review proposals with explicit apply and stale-plan rejection. | `v0.7.0` candidate | Drift detection, impact analysis, and Agent Computer workspace |
| P6 | Graph Explorer | Teams can inspect intent, evidence, drift, impact, synchronization proposals, and agent activity visually. | `v0.8.0` | Stable insight queries, policy status, synchronization records, and agent audit model |

## P0 — Restore the Public Automation Gate

The immediate operational requirement is to add the already prepared GitHub Actions workflow that runs Ruff linting, formatting checks, the test suite, distribution builds, and an installed-wheel CLI smoke test for `main` and pull requests. The workflow remains deferred because the GitHub publishing credential did not have permission to create or update workflow files.

**Done when:** the workflow is version-controlled at `.github/workflows/ci.yml`, a run succeeds on `main`, a pull-request run is visible, and Intent Kit’s own graph includes CI evidence or a link to the successful run.

**Risk control:** the workflow must use only repository-local commands and no third-party secret or deployment action.

## P1 — Graph Insight (`v0.3.0`)

Graph Insight activates the core promise of Intent Graph Development. Instead of merely preserving relationships, Intent Kit will provide deterministic answers about source drift, graph impact, proof coverage, and evidence freshness.

### Scope

| Capability | Command | Expected behavior |
|---|---|---|
| Source drift scan | `intentkit drift` | Re-hash imported artifacts, compare them with recorded provenance, and report unchanged, changed, missing, and unsupported source records. |
| Node impact report | `intentkit impact NODE-ID` | Traverse typed graph edges in both directions and list linked outcomes, requirements, decisions, tasks, proof obligations, and evidence. |
| Source impact report | `intentkit impact --source PATH` | Find graph nodes whose provenance points to a matching source artifact or resolved source path. |
| Proof gap summary | `intentkit impact NODE-ID --proof-gaps` | Highlight reachable planned, active, failed, stale, or missing proof evidence. |
| Markdown projection | `intentkit report` or rendered insight section | Generate a stable review artifact appropriate for Git review and issue discussion. |

### Acceptance Gate

A complete fixture must demonstrate a changed imported `spec.md` and a changed `tasks.md`. Tests must prove that drift is detected, source hashes remain deterministic, direct and transitive impact paths are stable, task-to-story and requirement-to-outcome links appear, and proof gaps are correctly identified. Intent Kit must dogfood the command against its own self-hosted graph.

## P2 — Policy Packs (`v0.4.0` candidate)

Policy Packs are delivered on `main`. The shipped `release-critical`, `migration`, and `documentation` packs create graph-visible proof and review defaults, while `.intent/policies.json` supports strictly validated local team packs. Explicit shaping flags take precedence over pack defaults, and packs remain declarative rather than executable.

| Pack example | Expected behavior |
|---|---|
| `release-critical` | Requires explicit evidence, freshness expectations, review metadata, and all required checks before verification. |
| `migration` | Requires provenance, a source snapshot, drift awareness, and an import-review record. |
| `documentation` | Uses lower-risk, lightweight existence/content proof checks and focused review notes. |

**Done when:** packs are declared in local configuration, can be applied from `shape`, appear in graph properties and Markdown, and validate against a documented policy contract.

## P3 — Controlled Checker Extensibility (`v0.5.0` candidate)

Controlled external checker execution is delivered on `main`. Each project must explicitly allowlist a local checker identity and version, pin a manifest digest, pin its Python entrypoint digest, and use a bounded JSON subprocess protocol. Package discovery, network access, and sandbox claims remain out of scope.

**Delivered controls:** explicit allowlisting, checker identity and version pinning, manifest and entrypoint digest validation, structured results, timeout handling, a minimal execution environment, and immutable audit evidence. A modified or incompatible checker is rejected before execution.

## P4 — Agent Computer Foundation (`v0.6.0` candidate)

The Agent Computer is delivered on `main`. It provides a language-agnostic JSON protocol for graph inspection, policy and checker discovery, bounded project file access, named quality commands, and an agent-owned scratch workspace. Graph and workspace changes use a proposal-first flow and require explicit `--apply`; all actions route through the existing policy, checker, proof, evidence, persistence, and rendering layers.

**Delivered controls:** no arbitrary shell; no direct graph-file writes; no network, browser, credentials, VM/container sandbox, or graphical desktop claim; project containment; scratch-workspace containment; and append-only local audit records.

## P5 — Incremental Spec Kit Synchronization (`v0.7.0` candidate)

Reviewed incremental synchronization is delivered on `main`. It compares the current source feature with the canonical graph, produces a deterministic proposal containing node and link changes, source digests, impacted graph paths, and proof gaps, then applies only the exact proposal after explicit approval. Source artifacts are read-only, matching source records preserve stable graph IDs, and any source or graph change after review invalidates the proposal.

**Delivered controls:** proposal and apply records under `.intent/sync-proposals/`; source-key matching; source-managed task status refresh; preservation of Intent Kit metadata outside source-managed fields; relationship reconciliation; stale-plan rejection; CLI and Agent Computer proposal/apply workflows; and source immutability.

## P6 — Graph Explorer (`v0.8.0`)

A visual surface becomes valuable only after the graph queries are stable. It should start as a local, read-only explorer of the existing graph rather than a collaborative cloud product.

**Initial views:** outcome-to-proof path, evidence register, source-drift dashboard, proof coverage and gaps, policy status, and recent import/synchronization activity.

**Done when:** the explorer renders the self-hosted graph correctly, deep-links to nodes and source provenance, and does not become a second source of truth.

## Cross-Cutting Release Discipline

Every milestone follows the same delivery sequence:

1. Write a concise design and define the typed graph changes.
2. Add deterministic unit and end-to-end CLI tests before introducing release behavior.
3. Update the README, command help, changelog, and focused reference documentation.
4. Dogfood the feature on Intent Kit where it applies.
5. Run linting, formatting, tests, source/wheel build, and installed-command smoke validation.
6. Commit and push only after the gate passes.
7. Publish a tagged GitHub release only after user approval.

## Current Next Action

The active product increment is **P6 — Graph Explorer**. It will provide a local, read-only view of the canonical graph, evidence, drift, impact, policy status, synchronization proposals, and agent activity without becoming a second source of truth.
