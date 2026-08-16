# Importing Existing Spec Kit Features

Intent Kit can import a completed **Spec Kit feature directory** into a new local Intent Kit graph. The importer is designed for migration and assessment: it reads rendered Markdown artifacts, creates typed graph nodes with source provenance, and never writes to the source directory.

## Intended Use

Use the importer when a feature already has a Spec Kit `spec.md`, with optional `plan.md` and `tasks.md`, and you want to review it through Intent Kit’s outcome → requirement → decision → implementation-task graph. The import is intentionally **one-way and conservative**. It creates a fresh graph representation of the source as it exists at import time; it does not modify, synchronize, or regenerate Spec Kit artifacts.

## Command

Initialize an empty Intent Kit project first, then import an explicit feature directory.

```bash
intentkit init --path ./intent-migration --project-name "Checkout Safety"
intentkit import-speckit ../legacy-project/specs/001-checkout-safety --path ./intent-migration
```

The source argument must be a directory containing `spec.md`. The optional `plan.md` and `tasks.md` files are used when present. The command saves the graph and regenerates `intent/intent.md`, `intent/design.md`, `intent/evidence.md`, and `intent/traceability.md`.

## Supported Artifact Conventions

The importer uses the stable rendered Markdown conventions emitted by Spec Kit templates. It recognizes the following structures.

| Source artifact | Supported convention | Requirement |
|---|---|---|
| `spec.md` | `# Feature Specification: …`, `### User Story N - … (Priority: PN)`, `**FR-NNN**`, and `**SC-NNN**` entries | Required |
| `plan.md` | `## Summary` and `## Technical Context` sections | Optional |
| `tasks.md` | Markdown checklist tasks such as `- [ ] T001 [P] [US1] …`, grouped under `## Phase …` headings | Optional |

Artifacts that do not follow these conventions are not rewritten or rejected unless `spec.md` is absent. Unsupported or unrecognized content is simply not mapped. Review the import summary and generated Markdown after every migration.

## Graph Mapping

| Spec Kit content | Intent Kit node | Relationship | Key imported properties |
|---|---|---|---|
| Feature title and user description | Outcome | Root of the imported feature | Success measures from `SC-NNN` entries |
| User story | Requirement | `requirement → outcome` (`derives_from`) | Story label, priority, independent test, acceptance scenarios |
| Functional requirement (`FR-NNN`) | Requirement | `requirement → outcome` (`derives_from`) | Source identifier |
| Plan summary and technical context | Decision | Standalone design record | Source kind `speckit_plan` |
| Task (`TNNN`) | Implementation task | `task → story requirement` (`implements`) when a matching `[USN]` label exists | Phase, story label, parallel flag, completion state |

Completed task checkboxes become `verified` implementation tasks. Unchecked tasks become `planned`. Setup and shared tasks without a `[USN]` label are retained as unlinked implementation-task nodes and appear in the generated design view.

## Provenance and Review

Every imported node contains a `provenance` object in its properties. It records the following information:

```json
{
  "importer": "intentkit.speckit",
  "source_root": "/absolute/path/to/spec-kit-feature",
  "artifact": "spec.md",
  "sha256": "sha256:…",
  "line": 26
}
```

The SHA-256 digest applies to the complete source artifact at import time. The source line points to the recognized heading or checklist entry. Together, they let reviewers distinguish imported context from native Intent Kit work and identify drift later.

## Idempotency and Safety

A single source directory may be imported into a graph only once. Intent Kit rejects a second import from the same resolved source root instead of silently creating duplicate requirements or tasks. To refresh a changed feature, use the delivered review-first [`sync-speckit`](speckit-sync.md) workflow: it creates a deterministic proposal, requires explicit apply, preserves matching graph identifiers, and rejects stale source or graph state.

The importer has no network access, executes no source code, and writes only to the destination Intent Kit project. It does not follow references from `spec.md`, parse arbitrary linked files, or run commands described in source artifacts.

## Current Limitations

The importer deliberately excludes automatic synchronization, conflict resolution, plan/task-to-functional-requirement links, semantic matching beyond explicit `[USN]` task labels, source-file discovery from `.specify/feature.json`, and migration of research, data model, contract, or checklist artifacts. Delivered incremental synchronization remains an explicit review-driven operation rather than an implicit background update.
