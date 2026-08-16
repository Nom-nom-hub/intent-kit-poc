# Intent Kit POC

**Intent Kit** is a local-first proof of concept for **Intent Graph Development (IGD)**. It preserves a lightweight, command-driven development experience while storing the underlying methodology as a typed, version-controlled graph of outcomes, requirements, decisions, proof obligations, and evidence.

> **Design principle:** Keep the interface linear for people; keep the system model graph-shaped for agents.

The POC intentionally focuses on one essential thesis: **a requirement should carry explicit, stable links to why it exists, how it will be addressed, and what proves it.** Markdown files remain the everyday review interface, but they are deterministic projections of a local graph rather than the only place relationships exist.

## What the POC Demonstrates

| Capability | POC behavior |
|---|---|
| Local-first storage | Stores canonical graph data in `.intent/graph.json`, a readable and Git-friendly JSON file. |
| Stable intent objects | Creates predictable IDs such as `OUT-001`, `REQ-001`, `DEC-001`, `PRF-001`, and `EVD-001`. |
| Typed relationships | Records explicit links including `derives_from`, `addresses`, `requires_proof`, and `proves`. |
| Linear user workflow | Provides `init`, `capture`, `shape`, `prove`, `render`, and `status` commands. |
| Markdown projections | Generates `intent/intent.md`, `design.md`, `evidence.md`, and `traceability.md`. |
| Manual collaboration | Preserves text inside a clearly marked **Manual Notes** region during future renders. |
| Proof status | Links evidence to proof obligations and marks them `verified`, `failed`, or active. |

## POC Scope

The POC is deliberately not a production system. It does **not** yet include agent integrations, a visual graph explorer, direct Spec Kit import, GitHub/Jira synchronization, CI/telemetry adapters, automatic repository mapping, role-based access control, or sophisticated merge/conflict resolution. Those are later roadmap capabilities, not safe assumptions for the first build.

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
  --proof-title "Prove retries are safe" \
  --proof-description "A repeated confirmation returns exactly one order."

PYTHONPATH=src python3 -m intentkit prove PRF-001 "Payment contract test" \
  --path ./demo-project \
  --description "The retry contract passed against the payment sandbox." \
  --source "tests/test_payment_contract.py" \
  --result pass

PYTHONPATH=src python3 -m intentkit status --path ./demo-project
```

## Command Model

| Command | Purpose |
|---|---|
| `intentkit init` | Creates `.intent/graph.json`, configuration, and empty Markdown projections. |
| `intentkit capture` | Records an active outcome with success measures and assumptions. |
| `intentkit shape` | Adds a requirement, plus optional decision and proof-obligation nodes. |
| `intentkit prove` | Records evidence against a proof obligation and updates its verification state. |
| `intentkit render` | Rebuilds Markdown projections from the canonical graph. |
| `intentkit status` | Shows graph counts and proof coverage. |

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

The tests cover graph integrity, deterministic IDs, persistence, Markdown projection, manual-note preservation, and a complete CLI workflow.

## Next Build Steps

The recommended next increment is **not** a broad feature expansion. It should add a read-only importer for existing Spec Kit feature artifacts, map `spec.md`, `plan.md`, and `tasks.md` into the graph with provenance, then validate change impact on one realistic brownfield feature.
