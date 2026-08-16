# Extending Intent Kit with Custom Proof Checkers

**Audience:** Intent Kit core maintainers, plug-in authors, and teams adding domain-specific verification.

**Applies to:** Intent Kit `0.2.0`

**Status:** Developer design and implementation guide. The typed contract, explicit local registry, graph-safe runner, CLI integration, and built-in checker are shipped in `0.2.0`; separately packaged checker discovery and isolation remain planned extensions.

## Purpose

A custom proof checker is an extension that evaluates a **proof obligation** and returns normalized, attributable evidence. It closes the gap between a requirement that says “this must be demonstrated” and an auditable record of how the claim was checked.

> **Core rule:** A checker may *observe and evaluate*. The Intent Kit core owns graph mutation, proof-state aggregation, persistence, rendering, and user-facing status.

This separation is deliberate. Intent Kit `0.2.0` stores a local, typed graph in `.intent/graph.json`; its graph nodes have a type, status, title, description, timestamps, and arbitrary JSON-compatible properties. It also persists directed typed edges and validates that both edge endpoints exist. [1] The manual `prove` command records an `evidence` node, while the shipped `check` command runs a trusted registered checker, records evidence, evaluates the proof policy, saves the graph atomically, and rerenders Markdown views. [2] A checker extension should preserve those invariants rather than bypass them.

The guide uses a `pytest`-style checker as an example because it demonstrates external process execution and machine-readable evidence. The same contract works for contract-test runners, accessibility scanners, schema validators, security policy checks, human review collectors, performance benchmarks, and production-signal evaluators.

## Current POC Baseline

Before introducing plug-ins, understand the existing model and its limits. The POC has six built-in node types, including `proof_obligation` and `evidence`, and it recognizes a `proves` relation. [1] The renderer locates evidence by reading incoming `proves` edges for each proof obligation, which means the canonical direction is always:

```text
Evidence node  ──proves──▶  Proof-obligation node
```

The renderer expects `evidence.properties["result"]` and `evidence.properties["source"]` when it writes `intent/evidence.md`. [3] The present CLI accepts a manual result of `pass`, `fail`, or `recorded`; it maps `pass` to `verified`, `fail` to `failed`, and otherwise keeps the proof active. [2]

| Current capability | Existing location | Implication for checkers |
|---|---|---|
| Typed node creation | `src/intentkit/kernel.py` | Checker output must eventually become an `EVIDENCE` node, not a new ad hoc node type. |
| Stable local IDs | `next_node_id()` in the kernel | The core, not the checker, allocates `EVD-###` identifiers. |
| Link validation | `IntentGraph.add_edge()` | The core must add `EVD → PRF` only after it confirms both nodes exist. |
| Atomic persistence | `GraphStore.save()` | Checkers must return an in-memory result; the core saves once after normalization and aggregation. |
| Markdown evidence view | `MarkdownRenderer._render_evidence()` | A custom result needs at least `result` and `source` properties for immediate renderer compatibility. |
| Manual proof command | `handle_prove()` in `cli.py` | The future `check` command should share the same recording path, not duplicate it. |

Intent Kit `0.2.0` ships an explicit in-process checker registry, normalized result taxonomy, a graph-safe runner, and `latest`, `all`, `any`, and `manual` aggregation policies. It does **not** yet ship external plug-in discovery, sandboxed execution, or automated evidence-freshness calculation. This guide documents the shipped foundation and the compatible path to those later additions.

## Extension Architecture

The target extension is a narrow, testable subsystem with five responsibilities. The graph kernel remains the source of truth. A checker runner provides lifecycle orchestration. Checkers provide domain-specific evaluation. A registry discovers and authorizes checkers. The existing renderer remains a projection layer.

```mermaid
flowchart LR
    A[Proof obligation PRF-001] --> B[Proof runner]
    B --> C[Registry / allowlist]
    C --> D[Custom checker]
    D --> E[Normalized CheckResult]
    E --> F[Core evidence recorder]
    F --> G[EVD-001 node]
    G --> H[PROVES edge]
    H --> I[Proof-state aggregator]
    I --> J[GraphStore.save]
    J --> K[MarkdownRenderer.render]
```

The core must never give an extension direct write access to `IntentGraph`, `GraphStore`, or rendered files. If a checker can write the graph directly, it can create malformed edges, set unrelated requirement state, omit provenance, or leave a partial update after a failed process. A checker returning a value object gives the core a single validation and persistence boundary.

### Recommended module layout

```text
src/intentkit/
  kernel.py                   # Existing graph, status, edge, and store primitives
  renderer.py                 # Existing Markdown projections
  cli.py                      # Existing commands; add `check`
  proof_checkers/
    __init__.py               # Public extension contract
    models.py                 # CheckRequest, CheckResult, artifact schemas
    registry.py               # Built-ins, entry-point discovery, allowlist validation
    runner.py                 # Execution, normalization, graph recording, aggregation
    builtin/
      pytest_checker.py       # Example in-core checker
      json_schema_checker.py  # Optional second in-core checker
  tests/
    test_proof_checker_contract.py
    test_proof_runner.py
    test_pytest_checker.py
```

This structure keeps the kernel independent of extension discovery and process execution. A project that does not enable custom checkers continues to use the existing `prove` path unchanged.

## Contract: What a Checker Receives and Returns

Python’s `Protocol` mechanism is a good fit for this boundary because it describes structural compatibility without forcing checker authors to inherit a runtime base class. Python’s documentation specifically notes that a protocol with `__call__` can express detailed callable signatures that a broad `Callable` annotation cannot. [4]

The following models are intentionally JSON-compatible at their boundaries. They are safe to log, persist as evidence properties, and render without custom serializers.

```python
# src/intentkit/proof_checkers/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from intentkit.kernel import IntentGraph, Node


class CheckState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class CheckerDescriptor:
    checker_id: str  # e.g., "org.example.pytest"
    version: str  # semantic version of the checker implementation
    display_name: str
    supported_kinds: tuple[str, ...]
    needs_network: bool = False
    needs_subprocess: bool = False


@dataclass(frozen=True, slots=True)
class Artifact:
    name: str
    path: str | None = None  # project-relative path only
    digest_sha256: str | None = None
    media_type: str | None = None


@dataclass(frozen=True, slots=True)
class CheckRequest:
    project_root: Path
    graph: IntentGraph  # treat as read-only snapshot
    obligation: Node  # always a PROOF_OBLIGATION node
    config: Mapping[str, Any]
    run_id: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class CheckResult:
    state: CheckState
    summary: str  # one concise, human-readable sentence
    details: str = ""  # bounded diagnostic text; no secrets
    source: str = ""  # test path, CI job URL, review record, etc.
    artifacts: tuple[Artifact, ...] = ()
    metrics: Mapping[str, float | int | str | bool] = field(default_factory=dict)
    external_run_id: str | None = None


class ProofChecker(Protocol):
    @property
    def descriptor(self) -> CheckerDescriptor: ...

    def can_check(self, request: CheckRequest) -> bool: ...

    def run(self, request: CheckRequest) -> CheckResult: ...
```

The `graph` object in `CheckRequest` is a convenience for reading linked requirements, decisions, policy properties, and previous evidence. It is not a permission to mutate. Enforce this convention by passing a deep-frozen snapshot in a production implementation, or by documenting that mutations are ignored because only the runner’s post-check graph instance is saved.

### Required output semantics

| Field | Requirement | Why it matters |
|---|---|---|
| `state` | Must be one of `pass`, `fail`, `inconclusive`, `error`, or `skipped`. | Distinguishes a failed claim from a broken checker or an intentionally skipped run. |
| `summary` | One redacted, action-oriented sentence. | Appears in evidence reports and CLI output. |
| `details` | Bounded diagnostic text; truncate or store a file reference for large output. | Keeps `graph.json` reviewable and prevents secret/log sprawl. |
| `source` | Stable local path, CI identifier, review record, or immutable URL. | Provides provenance visible in the existing Markdown renderer. [3] |
| `artifacts` | Project-relative references plus digests when available. | Enables later evidence-freshness and artifact-integrity checks. |
| `metrics` | Scalar JSON-compatible values only. | Enables aggregation without a custom object store. |
| `external_run_id` | Optional but recommended for CI or remote tools. | Supports navigation back to an authoritative external run. |

A checker must return a `CheckResult` for an expected negative result. For example, “the accessibility scan found three critical violations” is a `fail`, not an exception. Reserve `error` for failures in checker execution itself: missing binary, invalid configuration, timeout, malformed output, or unavailable required service.

## The Graph Recording Contract

The proof runner translates a `CheckResult` into the existing graph schema. It must add one immutable evidence node per execution attempt; never overwrite older evidence. Historical evidence is useful when a result changes, when debugging a checker, or when proving that an obligation was previously satisfied before a relevant change.

### Evidence properties

The following schema extends the POC’s existing `result` and `source` keys without breaking its renderer.

```json
{
  "result": "pass",
  "source": "tests/test_payment_contract.py",
  "checker": {
    "id": "org.example.pytest",
    "version": "1.0.0"
  },
  "run": {
    "id": "run-20260816T140501Z-a12bc3",
    "executed_at": "2026-08-16T14:05:01+00:00",
    "duration_ms": 842,
    "input_fingerprint": "sha256:..."
  },
  "summary": "Payment retry contract passed against the sandbox.",
  "details": "1 passed in 0.22s",
  "artifacts": [
    {
      "name": "JUnit XML",
      "path": "artifacts/payment-contract.xml",
      "digest_sha256": "...",
      "media_type": "application/xml"
    }
  ],
  "metrics": {
    "tests_total": 1,
    "tests_failed": 0
  }
}
```

The core should add the edge as follows:

```python
graph.add_edge(evidence.id, obligation.id, RelationType.PROVES)
```

Do **not** reverse the direction. The existing Markdown renderer calls `graph.incoming(obligation.id, RelationType.PROVES)` and treats each source node as evidence. [3]

### Node status mapping

The current `NodeStatus` enum has no `error`, `inconclusive`, `skipped`, or `stale` values. Preserve compatibility by retaining the richer execution state in `evidence.properties["result"]` and using the following default mapping.

| Check result | Evidence node status | Immediate proof obligation state | Interpretation |
|---|---|---|---|
| `pass` | `verified` | Determined by aggregation policy | The checker positively supported the claim. |
| `fail` | `failed` | Determined by aggregation policy | The checker evaluated the claim and found it false. |
| `inconclusive` | `active` | `active` | Evidence is insufficient; no truth claim is made. |
| `error` | `active` | `active` | The checker was unable to execute reliably. |
| `skipped` | `active` | `active` | The run was intentionally not performed. |

A future schema revision may add explicit `INCONCLUSIVE`, `ERROR`, `SKIPPED`, and `STALE` node states. Do not add undocumented strings to `NodeStatus` in a plug-in; `IntentGraph.add_node()` and `set_status()` validate statuses through the enum. [1]

## Aggregation Policy for Multiple Checkers

The POC’s current `prove` command updates a proof obligation directly from one manual result. [2] That behavior is fine for the POC but insufficient when a requirement needs several independent checks, such as an API contract test, database migration rehearsal, and security review.

Store the target aggregation policy in `proof_obligation.properties`. A safe default is `all` for automated proof checkers.

```json
{
  "risk": "R3",
  "evaluation": "all",
  "required_checkers": [
    "org.example.pytest",
    "org.example.migration-rehearsal"
  ],
  "freshness": {
    "max_age_days": 14,
    "invalidate_on": ["schema", "payment-contract", "dependency:payments-sdk"]
  }
}
```

| Policy | Verified when | Failed when | Recommended use |
|---|---|---|---|
| `latest` | The most recent non-error check passes. | The most recent non-error check fails. | Temporary compatibility mode for the existing manual `prove` experience. |
| `all` | Every required checker has a current pass. | Any required checker has a current fail. | Default for safety, integration, and compliance obligations. |
| `any` | At least one eligible checker has a current pass. | Every eligible checker has completed and failed. | Alternative implementation paths where one valid proof is sufficient. |
| `manual` | A human explicitly marks the obligation verified after reviewing evidence. | A human explicitly marks it failed. | Qualitative UX, design, legal, or governance evaluations. |

An `error`, `inconclusive`, or `skipped` result must never be treated as a passing result. For `all`, keep the obligation `active` until all required checkers have current results; for `any`, keep it `active` until a checker passes or all required alternatives have completed with failures.

## Implementing the Core Runner

The runner is the only component that turns a `CheckResult` into graph changes. It validates the target node, resolves an allowlisted checker, builds a read-only request, records immutable evidence, recomputes the obligation state, saves once, and regenerates Markdown.

```python
# src/intentkit/proof_checkers/runner.py
from __future__ import annotations

from hashlib import sha256
from time import perf_counter
from uuid import uuid4

from intentkit.kernel import GraphStore, NodeStatus, NodeType, RelationType, utc_now
from intentkit.renderer import MarkdownRenderer
from .models import CheckRequest, CheckResult, CheckState
from .registry import CheckerRegistry


class ProofRunner:
    def __init__(self, store: GraphStore, registry: CheckerRegistry):
        self.store = store
        self.registry = registry

    def run(self, obligation_id: str, checker_id: str, config: dict) -> CheckResult:
        graph = self.store.load()
        obligation = graph.get_node(obligation_id)
        if obligation.type != NodeType.PROOF_OBLIGATION.value:
            raise ValueError(f"{obligation_id} is not a proof obligation")

        checker = self.registry.resolve(checker_id)
        run_id = f"run-{uuid4().hex[:16]}"
        request = CheckRequest(
            project_root=self.store.project_root,
            graph=graph,
            obligation=obligation,
            config=config,
            run_id=run_id,
            timeout_seconds=int(config.get("timeout_seconds", 60)),
        )
        if not checker.can_check(request):
            result = CheckResult(
                state=CheckState.SKIPPED,
                summary="Checker does not support this proof obligation.",
                source=f"checker:{checker.descriptor.checker_id}",
            )
        else:
            started = perf_counter()
            result = checker.run(request)
            duration_ms = int((perf_counter() - started) * 1000)
            result = add_run_metric(result, duration_ms)

        evidence = graph.add_node(
            NodeType.EVIDENCE,
            title=f"{checker.descriptor.display_name}: {result.summary}",
            description=result.details or result.summary,
            status=evidence_status(result.state),
            properties=serialize_result(result, checker.descriptor, run_id),
        )
        graph.add_edge(evidence.id, obligation.id, RelationType.PROVES)
        graph.set_status(obligation.id, aggregate_obligation_status(graph, obligation.id))
        self.store.save(graph)
        MarkdownRenderer(self.store.project_root).render(graph)
        return result


def evidence_status(state: CheckState) -> NodeStatus:
    if state is CheckState.PASS:
        return NodeStatus.VERIFIED
    if state is CheckState.FAIL:
        return NodeStatus.FAILED
    return NodeStatus.ACTIVE
```

In production, wrap `checker.run()` in exception handling at the runner boundary. Convert expected operational failures—`TimeoutExpired`, executable not found, malformed scanner report, and network unavailability—into an `error` result. Preserve a concise error category in graph properties, but do not write raw stack traces, secret-bearing command lines, access tokens, or environment values into `graph.json`.

### Fingerprinting inputs and artifacts

A proof is meaningful only for a known input state. The runner should calculate a stable `input_fingerprint` from the checker identity, checker version, normalized configuration, referenced obligation properties, target file digests, and relevant lock/config files. The first release can store the digest without actively interpreting freshness; a later freshness engine can compare it with the current project state.

Use explicit file allowlists from checker configuration. Do not hash all files in a repository by default; that can be expensive, leak filenames into output, and create spurious invalidations.

## Building a Custom Checker: Pytest Example

This example checks an obligation that declares `properties["checker_kind"] = "pytest"`. It runs a configured local test target, classifies the return code, and records a bounded summary. It does not mutate the graph.

```python
# my_company_intent_checkers/pytest_checker.py
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from intentkit.proof_checkers.models import (
    CheckRequest,
    CheckResult,
    CheckState,
    CheckerDescriptor,
)


class PytestChecker:
    @property
    def descriptor(self) -> CheckerDescriptor:
        return CheckerDescriptor(
            checker_id="com.example.pytest",
            version="1.0.0",
            display_name="Pytest",
            supported_kinds=("pytest",),
            needs_subprocess=True,
        )

    def can_check(self, request: CheckRequest) -> bool:
        return request.obligation.properties.get("checker_kind") == "pytest"

    def run(self, request: CheckRequest) -> CheckResult:
        targets = request.config.get("targets", [])
        if (
            not isinstance(targets, list)
            or not targets
            or not all(isinstance(item, str) for item in targets)
        ):
            return CheckResult(
                state=CheckState.ERROR,
                summary="Pytest checker requires a non-empty string list of targets.",
                source="checker:com.example.pytest",
            )

        resolved_targets = [
            self._resolve_target(request.project_root, target) for target in targets
        ]
        command = [sys.executable, "-m", "pytest", "-q", *[str(item) for item in resolved_targets]]
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(request.project_root / "src"),
        }
        try:
            completed = subprocess.run(
                command,
                cwd=request.project_root,
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                state=CheckState.ERROR,
                summary=f"Pytest checker timed out after {request.timeout_seconds} seconds.",
                source=" ".join(command[:4]),
            )
        except OSError as exc:
            return CheckResult(
                state=CheckState.ERROR,
                summary="Pytest checker could not start.",
                details=type(exc).__name__,
                source=" ".join(command[:4]),
            )

        output = (completed.stdout + "\n" + completed.stderr).strip()
        bounded_output = output[-4000:]
        if completed.returncode == 0:
            return CheckResult(
                state=CheckState.PASS,
                summary="Configured pytest targets passed.",
                details=bounded_output,
                source=" ".join(command),
                metrics={"exit_code": completed.returncode},
            )
        if completed.returncode == 1:
            return CheckResult(
                state=CheckState.FAIL,
                summary="One or more configured pytest targets failed.",
                details=bounded_output,
                source=" ".join(command),
                metrics={"exit_code": completed.returncode},
            )
        return CheckResult(
            state=CheckState.ERROR,
            summary=f"Pytest exited unexpectedly with code {completed.returncode}.",
            details=bounded_output,
            source=" ".join(command),
            metrics={"exit_code": completed.returncode},
        )

    @staticmethod
    def _resolve_target(project_root: Path, target: str) -> Path:
        candidate = (project_root / target).resolve()
        if project_root not in candidate.parents and candidate != project_root:
            raise ValueError("Checker target must remain inside the project root.")
        if not candidate.exists():
            raise ValueError(f"Checker target does not exist: {target}")
        return candidate
```

The checker uses `subprocess.run()` with an argument sequence, captured output, an explicit timeout, and `shell=False` (the default). Python recommends `run()` for use cases it can handle and notes that a sequence of arguments is generally preferred because it avoids manual escaping and quoting. [6] This example also resolves test targets beneath the project root before execution and passes a minimal environment rather than forwarding all potentially sensitive variables.

### Example obligation configuration

```json
{
  "id": "PRF-001",
  "type": "proof_obligation",
  "title": "Payment retry contract passes",
  "description": "A repeated confirmation returns one order and no second charge.",
  "status": "planned",
  "properties": {
    "risk": "R3",
    "checker_kind": "pytest",
    "evaluation": "all",
    "required_checkers": ["com.example.pytest"]
  }
}
```

The shipped runner is exposed through the generic CLI command:

```bash
intentkit check PRF-001 --checker com.example.pytest \
  --config '{"targets":["tests/test_payment_contract.py"],"timeout_seconds":60}'
```

The command parser should treat `--config` as JSON, validate it against the checker’s documented schema, and refuse unknown or disabled checker IDs before loading any plug-in code.

## Registry and Plug-in Discovery

Start with an explicit in-process registry for built-ins. It is the smallest, safest deployment model and requires no packaging behavior.

```python
registry.register(PytestChecker())
```

When separately distributed packages are needed, Python package metadata entry points provide a standard discovery mechanism. The Python Packaging Authority describes package metadata entry points as a way for a distribution to announce a particular kind of plug-in, and recommends discovering them with `importlib.metadata.entry_points()`. [5]

### Plug-in package declaration

```toml
# pyproject.toml in the checker package
[project]
name = "my-company-intent-checkers"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["intentkit>=0.2,<0.3"]

[project.entry-points."intentkit.proof_checkers"]
pytest = "my_company_intent_checkers.pytest_checker:PytestChecker"
```

### Controlled discovery

Discovery must not equal authorization. Loading an entry point imports third-party code into the Intent Kit process. Use the following staged approach:

| Stage | Required control |
|---|---|
| Discover | List entry points in `intentkit.proof_checkers`; do not execute them while listing. |
| Allowlist | Compare the resolved checker ID and package distribution to `.intent/checkers.json`. Default deny for unknown IDs. |
| Load | Import the explicit, allowed entry point. Catch import errors and report them as checker availability issues. |
| Validate | Inspect descriptor fields, ensure the checker ID is unique, and reject incompatible API versions. |
| Configure | Validate checker-specific configuration before `run()`. Do not pass arbitrary CLI text directly to a checker. |
| Execute | Apply timeouts, path controls, and a redacted environment appropriate to the checker’s declared capabilities. |

A project-level allowlist can begin as simple, reviewable JSON:

```json
{
  "enabled": {
    "com.example.pytest": {
      "distribution": "my-company-intent-checkers",
      "version_specifier": ">=1.0,<2.0",
      "allowed_in_ci": true,
      "network": false,
      "timeout_seconds": 60
    }
  }
}
```

Avoid automatic remote download, self-updates, or unchecked URL-based checker installation. A local-first tool should make the origin, version, capability request, and enablement decision visible in Git review.

## CLI Integration Pattern

Add a single `check` command rather than embedding checker-specific flags in the core CLI. The core command remains generic; checker configuration is namespaced and validated by the selected checker.

```python
check = subparsers.add_parser("check", help="Run an allowlisted proof checker.")
add_path(check)
check.add_argument("obligation", help="Proof obligation ID.")
check.add_argument("--checker", required=True, help="Allowlisted checker ID.")
check.add_argument("--config", default="{}", help="Checker configuration as a JSON object.")
check.set_defaults(handler=handle_check)
```

`handle_check()` should parse configuration as JSON, create `GraphStore(args.path)`, load the configured registry, invoke `ProofRunner.run()`, print the result summary, and return a nonzero CLI exit code for `fail` or `error`. It should still record valid failing evidence before returning a nonzero exit code; that record is the point of the system.

| Checker state | Suggested CLI exit code | Graph behavior |
|---|---:|---|
| `pass` | `0` | Record evidence and allow aggregation to verify the obligation. |
| `fail` | `1` | Record evidence and allow aggregation to fail or keep active, per policy. |
| `inconclusive` | `2` | Record evidence, leave obligation active, explain what is missing. |
| `error` | `3` | Record bounded operational evidence, leave obligation active, surface remediation. |
| `skipped` | `0` or `2` by policy | Record reason, leave obligation active unless a policy explicitly permits skip. |

## Security and Operational Safety

Custom proof checkers are a code-execution boundary. Treat every third-party checker as privileged software, even if it only reads tests today.

### Non-negotiable safety rules

| Risk | Required mitigation |
|---|---|
| Shell injection | Use an argument list with `subprocess.run`; keep `shell=False`; never concatenate user-supplied strings into a command. [6] |
| Path traversal | Resolve every configured file path and require it to remain under an approved root. |
| Secret leakage | Pass a small explicit environment; redact command output and never persist tokens, headers, or environment dumps. |
| Unbounded execution | Set a timeout, output-size cap, artifact-size cap, and checker-specific concurrency limit. |
| Arbitrary plug-in loading | Require an allowlisted checker ID and verified distribution/version before loading entry points. |
| Graph corruption | Restrict graph writes to the core runner; validate then atomically save once. [1] |
| Network exfiltration | Declare `needs_network` in the descriptor, default it to false, and require explicit project approval for true. |
| Nondeterministic evidence | Record checker identity, version, normalized configuration, run ID, timestamps, and input/artifact digests. |

Run untrusted checkers in an isolated process or container once the project moves beyond a local developer POC. The checker contract remains the same; only the executor changes. A mature executor can enforce read-only source mounts, a writable temporary artifact directory, no network by default, CPU/memory quotas, and a narrow environment.

### Sensitive output policy

Checkers must treat raw stdout, stderr, HTTP bodies, scan reports, and test snapshots as potentially sensitive. The default evidence node should retain only a concise summary, an error category, bounded redacted details, and an artifact pointer/digest. Keep full reports in a controlled artifact store or a project-local ignored directory, with an explicit retention policy.

## Testing a Checker

A custom checker needs more than one happy-path test. Its contract governs evidence used in release decisions, so test both its evaluation logic and its integration with the graph.

| Test layer | Test objective | Example assertion |
|---|---|---|
| Unit | Validate `can_check()` and result classification. | Return code `0` produces `pass`; return code `1` produces `fail`; timeout produces `error`. |
| Contract | Validate the checker implements the required descriptor, support check, and run methods. | Registry rejects duplicate checker IDs or incompatible API versions. |
| Runner integration | Validate the core creates an immutable evidence node and the correct `EVD → PRF` edge. | `graph.incoming("PRF-001", PROVES)` contains the new evidence. |
| Aggregation | Validate `all`, `any`, `latest`, and `manual` policies. | An `all` obligation remains active after one pass and one required skipped check. |
| Negative security | Exercise traversal, malformed configuration, secret-like output, and timeouts. | `../../etc/passwd` is rejected before process execution. |
| Determinism | Repeat a check against unchanged inputs. | Same normalized input fingerprint; new evidence run is traceable but result is stable. |
| Renderer | Validate evidence remains visible in `intent/evidence.md`. | The `result` and `source` values are rendered by the existing projection. [3] |

A minimal integration test should create an outcome, requirement, and proof obligation; run a fake checker returning a fixed pass; then assert all of the following: an `EVD-001` node was created; its properties include checker provenance; its `PROVES` edge points to the proof obligation; the proof aggregation produced the expected state; and the renderer writes the evidence line.

## Compatibility Rules

Keep custom checkers compatible with the POC by following these rules.

1. **Do not add a new node type merely to store checker output.** Use `EVIDENCE` and namespaced properties.
2. **Do not add a relation string outside `RelationType` from a plug-in.** The graph validates relations through the enum. [1]
3. **Do not call `GraphStore.save()` inside a checker.** The runner must decide whether and when to commit a result.
4. **Do not mutate a requirement, outcome, or decision as a side effect of checking.** Create evidence and let documented aggregation rules affect only the targeted proof obligation.
5. **Do not use unstable source text alone as provenance.** Add checker ID, checker version, run ID, configuration fingerprint, and digests where possible.
6. **Do not silently treat unavailable checks as passes.** Use `error`, `inconclusive`, or `skipped` and leave proof verification unresolved.
7. **Do not require an external service for the core contract.** A checker may integrate with CI or a scanner, but the runner must still support local result recording and clear failure handling.

## Recommended Implementation Sequence

Implement in small, reversible steps.

| Increment | Deliverable | Acceptance criterion |
|---|---|---|
| 1 | `CheckState`, request/result models, and `ProofChecker` protocol | A fake in-process checker compiles and can return every normalized state. |
| 2 | `ProofRunner` and evidence recorder | A pass result creates `EVD-001`, links it to `PRF-001`, saves once, and renders Markdown. |
| 3 | `latest` aggregation policy | Existing manual `prove` behavior remains compatible. |
| 4 | Built-in checker and `intentkit check` | A local checker executes one safe, bounded command and records success/failure. |
| 5 | `all` and `any` aggregation | Multiple checker results produce the expected proof state. |
| 6 | Entry-point discovery and allowlist | A separately installed package can be enabled deliberately and rejected by default otherwise. |
| 7 | Isolation and freshness | High-risk checks can run with stronger process controls and evidence expiry logic. |

## Troubleshooting

| Symptom | Likely cause | Corrective action |
|---|---|---|
| Evidence is absent from `intent/evidence.md` | The edge is reversed or is not `proves`. | Create `EVD → PRF` using `RelationType.PROVES`. [3] |
| Graph save raises an enum error | A checker attempted to use an unsupported node status or relation. | Keep rich execution state in evidence properties; extend the core enum only through a schema change. [1] |
| Proof is verified despite a missing required check | Aggregation policy was not applied or required checker IDs were not normalized. | Use `all` by default and compare the current evidence set against `required_checkers`. |
| A failing test causes no evidence record | The CLI exits before calling the core recorder. | Record normalized failure evidence first; return CLI exit code after save/render. |
| A checker works locally but not in CI | It depends on inherited environment, working directory, or an unavailable executable. | Use explicit `cwd`, minimal environment, documented dependencies, and a bounded preflight check. |
| A plug-in appears in discovery but is rejected | It is not in the project allowlist or its descriptor/version conflicts. | Update `.intent/checkers.json` through reviewed configuration, not auto-enable logic. |
| `graph.json` contains huge or sensitive logs | The checker persisted raw process output. | Truncate/redact details; store full report externally with a pointer and digest. |

## Final Checklist for Plug-in Authors

Before publishing a checker, verify that it has a stable ID and version, returns the full normalized result shape, makes no graph or renderer writes, uses safe process/network boundaries, produces bounded and redacted diagnostics, records a trustworthy source, has unit and runner-integration tests, declares capabilities honestly, and documents its configuration schema and failure modes.

A good checker is not just a wrapper around a command. It is a **reproducible evidence producer** that helps Intent Kit answer: “What proof exists, under which conditions, for which claim, and can we still trust it?”

## References

[1]: ../src/intentkit/kernel.py "Intent Kit POC graph kernel"
[2]: ../src/intentkit/cli.py "Intent Kit POC command-line interface"
[3]: ../src/intentkit/renderer.py "Intent Kit POC Markdown renderer"
[4]: https://docs.python.org/3/library/typing.html "Python typing documentation: Protocol and callable contracts"
[5]: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/ "Python Packaging User Guide: Creating and discovering plugins"
[6]: https://docs.python.org/3/library/subprocess.html "Python subprocess documentation"
