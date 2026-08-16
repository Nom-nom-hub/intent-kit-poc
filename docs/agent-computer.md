# Agent Computer and Structured Agent Protocol

Intent Kit now gives an external agent a **project-scoped Agent Computer**. The agent can inspect the current intent graph, read bounded project files, use a dedicated scratch workspace, run a small named quality-command catalog, propose typed graph changes, and apply approved changes through the same policies, proof runner, and evidence model used by humans.

> **Design principle:** the Agent Computer is a controlled project capability, not an unrestricted shell or a second source of truth. Intent Kit remains the canonical graph, policy, proof, and evidence system.

## What Is Shipped

| Capability | Agent operation | Mutation rule |
|---|---|---|
| Graph state | `snapshot`, `status` | Read-only |
| Change reasoning | `drift`, `impact` | Read-only |
| Governance discovery | `policies`, `checkers` | Read-only |
| Project inspection | `computer.status`, `computer.list_files`, `computer.read_file` | Read-only; bounded UTF-8 reads |
| Quality actions | `computer.run` | Named commands only; audit logged |
| Scratch work | `computer.write_file` | Requires `--apply`; writes only under `.intent/agent-workspace/<session-id>/` |
| Intent changes | `capture`, `shape`, `prove`, `check` | Requires `--apply`; uses the regular graph, policy, checker, and evidence paths |

The protocol is language-agnostic. An agent framework can call the `intentkit` executable, send a JSON request, parse one JSON response, and make approval decisions without scraping human-oriented Markdown output.

## Protocol Envelope

Every request has this shape:

```json
{
  "protocol_version": 1,
  "request_id": "review-001",
  "operation": "impact",
  "arguments": {
    "node_id": "REQ-001"
  }
}
```

Submit the request inline or from a file:

```bash
intentkit agent --path ./project --request '{
  "protocol_version": 1,
  "request_id": "status-001",
  "operation": "status",
  "arguments": {}
}'

intentkit agent --path ./project --request-file ./agent-request.json
```

Responses are JSON on standard output. Successful reads set `"ok": true` and `"applied": false`. Validation and containment errors set `"ok": false` with a stable error code.

## Read Before Acting

An agent should establish context before proposing a change.

```json
{
  "protocol_version": 1,
  "request_id": "graph-001",
  "operation": "snapshot",
  "arguments": {
    "include_graph": true
  }
}
```

The graph snapshot and `impact` operation expose typed outcomes, requirements, decisions, proof obligations, evidence, policies, and traceability paths. `drift` exposes imported source-hash changes without touching either source files or the graph.

## The Project-Scoped Computer

The computer has a dedicated location inside each project:

```text
.intent/agent-workspace/<session-id>/
```

Agents can write notes, intermediate reports, proposed patches, test reports, or request payloads there only after explicit apply mode. Intent Kit records workspace writes and named command runs in `.intent/agent-computer-log.jsonl`. The log is deliberately excluded from normal Agent Computer inspection.

A typical workspace proposal is a two-step exchange:

```bash
# First response is a non-mutating preview.
intentkit agent --path ./project --request '{
  "protocol_version": 1,
  "request_id": "scratch-001",
  "operation": "computer.write_file",
  "arguments": {
    "session_id": "research-agent",
    "path": "analysis/change-plan.md",
    "content": "# Proposed change\n..."
  }
}'

# After an approval decision, apply the exact request.
intentkit agent --path ./project --apply --request-file ./approved-write.json
```

The named command catalog is intentionally small: `test`, `lint`, `format-check`, and `build`. An agent selects a command name; it cannot pass an arbitrary executable, command-line argument, shell expression, environment variable, or network destination through this interface.

## Explicit Apply for Graph Changes

All state-changing graph operations require `--apply`. Without it, Intent Kit returns a machine-readable proposal envelope and changes nothing.

```json
{
  "protocol_version": 1,
  "request_id": "shape-001",
  "operation": "shape",
  "arguments": {
    "title": "Verify contract export",
    "description": "The exported artifact must satisfy the checked contract.",
    "outcome_id": "OUT-001",
    "policy": "release-critical",
    "proof_checker_kind": "file_exists",
    "required_checkers": ["local.file-exists"]
  }
}
```

When applied, `shape` resolves the policy pack, creates graph nodes and typed edges, persists the canonical graph, and renders Markdown. `check` routes only to the regular checker registry; this means built-in and manifest-pinned external checkers retain their existing authorization and evidence rules.

## Trust Boundary

| Control | What it means |
|---|---|
| No arbitrary shell | The Agent Computer never accepts a command string, executable path, or shell syntax from an agent. |
| No network capability | The shipped workspace protocol exposes no network operation. A named command may still execute project code, so it must be treated as trusted project automation. |
| Project containment | Project reads must stay under the project root. Scratch writes must stay in the agent workspace. `.git`, the agent workspace, and the audit log are excluded from normal listings. |
| Explicit apply | Workspace writes and graph changes have a proposal-first flow. `--apply` is a deliberate operation-level authorization signal. |
| Typed graph changes | Agents cannot write `.intent/graph.json` directly through the protocol. Capture, shape, prove, and check use Intent Kit’s normal validation, policy, proof, evidence, persistence, and rendering layers. |
| Audit trail | Named command runs, workspace writes, and applied graph operations are recorded locally in the Agent Computer audit log. |

This release does **not** provide a graphical desktop, browser automation, VM/container isolation, arbitrary package installation, external credentials, network access, multi-agent collaboration, or remote persistent computers. Those should be introduced only with separate isolation, identity, approval, and observability controls.

## Recommended Agent Loop

1. Call `snapshot` or `status` to establish the graph and proof baseline.
2. Call `drift` and `impact` before changing imported or risk-bearing work.
3. Put long analysis and proposed artifacts in the agent workspace.
4. Submit a mutation request without `--apply` and surface the returned proposal for approval.
5. Resubmit the approved request with `--apply`.
6. Use `computer.run` for the named validation commands and `check` for approved proof checker execution.
7. Inspect `status` and `impact` again; cite graph IDs and evidence IDs in the agent’s report.

The repository’s own self-hosted graph uses this pattern to prove that Agent Computer capabilities are policy-aware and evidence-backed.
