# Graph Insight: Drift and Change Impact

Graph Insight is Intent Kit’s read-only analysis layer. It answers two practical review questions that document pipelines do not answer reliably on their own:

1. **Does an imported source artifact still match the graph record created from it?**
2. **If this graph node or source artifact changes, what intent, implementation work, proof obligations, and evidence should be reviewed?**

The commands read the local graph and local source artifacts only. They do not alter source documents, graph JSON, evidence, or rendered Markdown.

## Drift Detection

```bash
intentkit drift --path ./intent-migration
intentkit drift --path ./intent-migration --source ../project/specs/001-checkout/spec.md
```

The Spec Kit importer records a source root, relative artifact name, complete-artifact SHA-256 digest, source line, and importer identity on every imported node. `intentkit drift` groups nodes that share this provenance, re-hashes each tracked artifact, and reports one result per artifact.

| Status | Meaning | Exit behavior |
|---|---|---|
| `UNCHANGED` | The current file hash equals the recorded import hash. | Success (`0`) |
| `CHANGED` | The current file exists but its hash differs from the import record. | Review needed (`1`) |
| `MISSING` | The recorded source file no longer exists. | Review needed (`1`) |
| `UNSUPPORTED` | The recorded artifact would resolve outside its source root. | Review needed (`1`) |

An empty report is valid: it means the graph has no importer provenance matching the selected scope. `drift` then exits successfully and clearly states that no records matched.

### Source Matching

The optional `--source` parameter accepts either a source feature directory or a specific artifact path. Paths are resolved locally. A directory matches its recorded `source_root`; a file matches the resolved `source_root/artifact` path.

The path-containment check is intentional. A malformed provenance record must not cause `drift` to read an arbitrary path outside its recorded feature root.

## Impact Analysis

```bash
intentkit impact REQ-002 --path ./intent-migration
intentkit impact --source ../project/specs/001-checkout --path ./intent-migration
intentkit impact REQ-002 --proof-gaps --path ./intent-migration
```

`impact` starts at a graph node or the imported nodes associated with a source path. It follows both incoming and outgoing typed edges using a deterministic breadth-first traversal. This gives a reviewer the whole local context of a change rather than only a narrow downstream slice.

| Example link | Why it is traversed |
|---|---|
| `requirement → outcome` (`derives_from`) | A requirement change may affect the user or business outcome it supports. |
| `implementation task → requirement` (`implements`) | A requirement review should expose the work that implements it. |
| `requirement → proof obligation` (`requires_proof`) | A changed requirement may invalidate the proof claim. |
| `evidence → proof obligation` (`proves`) | A proof review should expose the evidence that currently supports it. |

The report shows each impacted node’s stable ID, type, status, traversal depth, and typed path from the root. If a reachable proof obligation is not `verified`, it appears in the **Proof gaps** summary.

### Proof-Gap Exit Behavior

`impact` normally exits successfully after producing a report, even when proof gaps exist. This keeps the command useful for exploratory review. Add `--proof-gaps` when a script or release check should fail on reachable, non-verified proof obligations. With that flag, the command exits `1` if one or more gaps are found.

## Recommended Review Workflow

Use Graph Insight as an explicit review step when an imported feature evolves:

1. Run `intentkit drift` after a source-specification, plan, or task-list change.
2. For every changed or missing artifact, run `intentkit impact --source …`.
3. Review the connected requirements, tasks, proof obligations, and evidence.
4. Use the findings to decide whether to create a fresh import now or await incremental synchronization support.
5. Re-run or replace evidence when a reachable proof obligation no longer describes the changed requirement.

The first release intentionally does not update imported nodes in place. Drift and impact provide the information needed for deliberate review; future incremental synchronization will apply a proposed delta only after review.

## Determinism and Limits

The implementation uses graph IDs and stable edge ordering to keep output predictable in tests and Git-based review. It finds the shortest discovered path to each connected node. It does not infer semantic equivalence, execute source code, follow web links, inspect repositories, or decide whether a changed artifact should be accepted. Those are human review decisions.
