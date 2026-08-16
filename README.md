# Intent Kit POC

![Intent Kit logo: a green intent graph with an integrated verification mark](assets/intent-kit-logo.png)

**Intent Kit** is a local-first proof of concept for **Intent Graph Development (IGD)**. It preserves a lightweight, command-driven development experience while storing the underlying methodology as a typed, version-controlled graph of outcomes, requirements, decisions, proof obligations, and evidence.

> **Design principle:** Keep the interface linear for people; keep the system model graph-shaped for agents.

The POC intentionally focuses on one essential thesis: **a requirement should carry explicit, stable links to why it exists, how it will be addressed, and what proves it.** Markdown files remain the everyday review interface, but they are deterministic projections of a local graph rather than the only place relationships exist.

## What the POC Demonstrates

| Capability | POC behavior |
|---|---|
| Local-first storage | Stores canonical graph data in `.intent/graph.json`, a readable and Git-friendly JSON file. |
| Stable intent objects | Creates predictable IDs such as `OUT-001`, `REQ-001`, `DEC-001`, `PRF-001`, and `EVD-001`. |
| Typed relationships | Records explicit links including `derives_from`, `addresses`, `requires_proof`, and `proves`. |
| Linear user workflow | Provides `init`, `capture`, `shape`, `prove`, `check`, `render`, and `status` commands. |
| Markdown projections | Generates `intent/intent.md`, `design.md`, `evidence.md`, and `traceability.md`. |
| Manual collaboration | Preserves text inside a clearly marked **Manual Notes** region during future renders. |
| Proof status | Links evidence to proof obligations, supports `latest`, `all`, `any`, and `manual` evaluation policies, and marks proofs `verified`, `failed`, or active. |
| Typed proof checks | Runs trusted in-process checkers that return normalized, provenance-rich evidence without direct graph-write access. |

## POC Scope

The POC is deliberately not a production system. It does **not** yet include agent integrations, a visual graph explorer, direct Spec Kit import, GitHub/Jira synchronization, CI/telemetry adapters, automatic repository mapping, role-based access control, external checker-package discovery, or sophisticated merge/conflict resolution. Those are later roadmap capabilities, not safe assumptions for the first build.

## Quick Start

The project uses only the Python standard library at runtime. From the repository root, run the commands below. Replace `demo-project` with your target directory.

```bash
PYTHONPATH=src python3 -m intentkit init --path ./demo-project --project-name "Checkout Safety"

PYTHONPATH=src python3 -m intentkit capture "Prevent duplicate orders" \
  --path ./demo-project \
  --description "Checkout retries must not create duplicate orders." \
  --success-measure "A repeated confirmation returns exactly one order."

PYTHONPATH=src python3 -m intentkit shape "Use idempotency keys" \
  --path ./demo-project \
  --description "Every confirmation request must carry an idempotency key." \
  --outcome OUT-001 \
  --risk R3 \
  --decision-title "Use provider idempotency keys" \
  --rationale "Provider-backed idempotency is the safest available approach." \
  --alternative "Time-window deduplication" \
  --proof-title "Prove the intent contract exists" \
  --proof-description "The generated intent contract must be present." \
  --proof-checker-kind file_exists \
  --proof-evaluation all \
  --required-checker local.file-exists

PYTHONPATH=src python3 -m intentkit check PRF-001 \
  --path ./demo-project \
  --checker local.file-exists \
  --config '{"path":"intent/intent.md","contains":"Intent Contract"}'

PYTHONPATH=src python3 -m intentkit status --path ./demo-project
```

## Command Model

| Command | Purpose |
|---|---|
| `intentkit init` | Creates `.intent/graph.json`, configuration, and empty Markdown projections. |
| `intentkit capture` | Records an active outcome with success measures and assumptions. |
| `intentkit shape` | Adds a requirement, plus optional decision and proof-obligation nodes. |
| `intentkit prove` | Records manually supplied evidence against a proof obligation and updates its verification state. |
| `intentkit check` | Runs a trusted registered checker, records immutable evidence with provenance, evaluates the proof policy, and rerenders Markdown. |
| `intentkit render` | Rebuilds Markdown projections from the canonical graph. |
| `intentkit status` | Shows graph counts and proof coverage. |

## Proof Checkers

Intent Kit now provides a **local-first proof-checker foundation**. Checkers receive a typed read-only request and return a normalized result (`pass`, `fail`, `inconclusive`, `error`, or `skipped`). The core runner—not the checker—creates the evidence node, adds the `EVD → PRF` `proves` edge, aggregates proof state, saves the graph, and regenerates Markdown.

| Built-in checker | Obligation property | Required configuration | Behavior |
|---|---|---|---|
| `local.file-exists` | `"checker_kind": "file_exists"` | `{"path": "project-relative-path"}` | Verifies a project-contained path exists; optional `contains` checks UTF-8 file content. |

The default registry is explicit and in-process: only trusted checkers bundled by Intent Kit are loaded. The extension guide at [`docs/custom-proof-checkers.md`](docs/custom-proof-checkers.md) defines the typed contract, evidence lifecycle, aggregation policies, testing expectations, and the path to separately packaged checkers with deliberate allowlisting.

## Local Data Model

```text
Outcome ← Requirement ← Decision
                 ↓
         Proof obligation ← Evidence
```

The POC records this graph as nodes plus typed directed edges. It makes the following questions queryable in a deterministic way:

| Question | Graph object |
|---|---|
| Why does this feature exist? | Outcome |
| What must be true? | Requirement |
| How will it be addressed? | Decision |
| What must be demonstrated? | Proof obligation |
| What was observed or executed? | Evidence |

## Generated Files

```text
.intent/
  config.json               # Small local configuration file
  graph.json                # Canonical, Git-friendly graph data
intent/
  intent.md                 # Outcomes and requirements
  design.md                 # Decisions and alternatives
  evidence.md               # Proof obligations and recorded evidence
  traceability.md           # Complete source → relation → target map
```

Each rendered Markdown file has a **Manual Notes** section with preservation markers. Edit inside that section for review context or links that must survive a subsequent `render` command.

## Verification

Run the test suite from the project root:

```bash
python3 -m pytest -q
```

The tests cover graph integrity, deterministic IDs, persistence, Markdown projection, manual-note preservation, checker registration, path containment, proof aggregation, and complete CLI workflows.

## Next Build Steps

The next recommended increment is **controlled external checker discovery**: package entry-point discovery behind a project allowlist, configuration validation, and isolated execution boundaries. After that, add a read-only importer for existing Spec Kit feature artifacts and validate change impact on one realistic brownfield feature.
