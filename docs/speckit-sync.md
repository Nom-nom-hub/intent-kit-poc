# Incremental Spec Kit Synchronization

Intent Kit can now synchronize a feature that was previously imported from Spec Kit. Synchronization is deliberately a **reviewed graph-update workflow**, not an automatic background refresh. It never modifies `spec.md`, `plan.md`, or `tasks.md`.

> **Operating rule:** generate a deterministic proposal, review the source delta and graph impact, then apply that exact proposal only with an explicit approval action. If the graph or source changes after review, Intent Kit rejects the proposal as stale.

## What Is Synchronized

The supported source surface remains the documented subset used by the initial importer.

| Source record | Stable synchronization key | Target graph record | Status behavior |
|---|---|---|---|
| Feature heading | `feature` | Outcome | Remains active unless changed outside the source-managed fields. |
| User story | `story:USN` | Requirement | Preserves the node ID and any Intent Kit status; refreshes source content and provenance. |
| Functional requirement | `functional:FR-NNN` | Requirement | Preserves the node ID and any Intent Kit status; refreshes source content and provenance. |
| Plan summary/context | `plan` | Decision | Preserves the node ID and status; refreshes source content and provenance. |
| Task | `task:TNNN` | Implementation task | Preserves the node ID; source checkbox status remains authoritative. |

Because provenance stores an artifact-level SHA-256 digest, an edited source artifact refreshes provenance on every record derived from that artifact. The proposal labels these as `updated`; the `changes` field distinguishes semantic fields such as `title`, `description`, and `status` from provenance changes.

## Review First, Apply Second

Generate a proposal for a previously imported feature. The source root must already appear in the graph’s Spec Kit provenance; `sync-speckit` cannot be used as an alternate importer:

```bash
intentkit sync-speckit ./specs/001-checkout-safety --path ./intent-project
```

The command writes a canonical review artifact to:

```text
.intent/sync-proposals/sync-<deterministic-id>.json
```

It reports the number of source changes, impacted graph nodes, and reachable proof gaps. The proposal includes the imported source digests, the graph digest at review time, node additions/updates/removals, relation additions/removals, impact node IDs, proof-gap IDs, and the explicit apply command.

Apply only the reviewed proposal:

```bash
intentkit sync-speckit ./specs/001-checkout-safety \
  --path ./intent-project \
  --proposal .intent/sync-proposals/sync-<deterministic-id>.json \
  --apply
```

Intent Kit regenerates the proposal against the current graph and current source before it writes anything. The apply fails if either side has changed, forcing a new review rather than silently accepting a stale plan. Successful application writes a sibling `.applied.json` record and regenerates the Markdown projections.

## Interpreting a Proposal

| Delta action | Meaning | Apply behavior |
|---|---|---|
| `unchanged` | The source-managed record and its provenance match the graph. | No node change. |
| `added` | A new supported source record appeared. | Create one typed node and its managed links. |
| `updated` | Source content, source status, or provenance changed. | Keep the same graph node ID; refresh source-managed fields. |
| `removed` | A previously imported source record is absent. | Remove that imported node and its attached edges only after explicit apply. |

Synchronization preserves metadata that Intent Kit owns outside the importer’s source-managed fields. For example, a requirement’s local policy metadata stays in the graph while its imported title, description, and provenance are refreshed. Task statuses are the exception: the task checklist is source-managed, so `[x]` and `[ ]` refresh the imported task’s verification state.

## Source and Graph Safety

| Safeguard | Behavior |
|---|---|
| Source immutability | The synchronizer only reads Spec Kit artifacts. It never writes into the source feature directory. |
| Stable node identity | Supported source keys match existing records and update them in place instead of creating duplicates. |
| Graph review | The proposal records additions, updates, removals, relation changes, reachable impact, and proof gaps before application. |
| Explicit approval | CLI application requires `--apply`. Agent application returns a proposal preview unless the caller sets `--apply`. |
| Stale-plan rejection | Current source digests and graph digest must reproduce the reviewed proposal exactly. |
| Relationship reconciliation | Source-managed `derives_from` and `implements` links are added or removed only as part of the approved plan. |
| Review log | Proposal and `.applied.json` records live under `.intent/sync-proposals/` and are suitable for Git review. |

## Agent Workflow

The Agent Computer protocol exposes synchronization without bypassing the same review boundary.

First request a proposal:

```json
{
  "protocol_version": 1,
  "request_id": "sync-review-001",
  "operation": "sync.propose",
  "arguments": {
    "source": "/workspace/specs/001-checkout-safety"
  }
}
```

The response contains the full proposal JSON. An agent can put a human-readable summary in `.intent/agent-workspace/<session-id>/`, call `impact` on affected nodes, and show the proposal to a reviewer.

To apply, resubmit the exact proposal after approval:

```json
{
  "protocol_version": 1,
  "request_id": "sync-apply-001",
  "operation": "sync.apply",
  "arguments": {
    "source": "/workspace/specs/001-checkout-safety",
    "proposal": { "...": "exact proposal returned by sync.propose" }
  }
}
```

Without `intentkit agent --apply`, Intent Kit returns a non-mutating preview. With `--apply`, it revalidates both source and graph, stores the reviewed proposal, applies the delta, writes the `.applied.json` record, regenerates Markdown, and appends an Agent Computer audit entry.

## Current Limits

Synchronization supports only the Spec Kit Markdown subset already supported by the importer and only for a source root that has previously been imported into the target graph. It does not merge arbitrary manual edits inside the source-managed title, description, provenance, or task status fields; source wins for those fields after approval. It does not perform three-way text merges, make changes to source artifacts, synchronize external issue trackers, or resolve concurrent multi-user edits. A stale proposal is intentionally rejected rather than guessed through.
