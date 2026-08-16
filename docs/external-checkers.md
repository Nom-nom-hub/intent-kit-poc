# Controlled External Checkers

Intent Kit can run a separately maintained proof checker only when the **current project explicitly allowlists it**. External checker discovery is disabled by default. Intent Kit does not scan installed packages, Python entry points, `PATH`, or a registry service for extensions.

> **Security boundary:** An external checker is still code that a trusted project maintainer has chosen to execute. Intent Kit provides explicit authorization, manifest and entrypoint digest pinning, a constrained JSON subprocess protocol, bounded output, a timeout, and a minimal environment. It does **not** claim to provide an operating-system sandbox, container isolation, filesystem virtualization, or protection from malicious code that a maintainer explicitly allowlists.

## Trust Model

| Layer | Required control | What it prevents |
|---|---|---|
| Discovery | No environment or package discovery; only `.intent/external-checkers.json` is read. | Accidental execution because a package happens to be installed. |
| Authorization | One explicit `checker_id` and exact version per allowlist entry. | Unreviewed checker identities and silent version changes. |
| Manifest integrity | The allowlist pins the SHA-256 digest of the manifest. | Editing a manifest after it was approved. |
| Entrypoint integrity | The manifest pins the SHA-256 digest of the executable script. | Replacing the checker code without an explicit manifest update. |
| Capabilities | Network declaration must be `false` in this release. | A manifest cannot claim network access through the supported contract. |
| Execution | The runner invokes `python -I`, supplies only JSON on standard input, expects one JSON result, bounds output, sets a timeout, and strips ambient Python import configuration. | Common protocol mistakes, uncontrolled log growth, and accidental user-site imports. |
| Persistence | The checker cannot receive `GraphStore` or write graph state through the API. The core records evidence after validating the result. | Malformed graph mutation and partial persistence through the Intent Kit contract. |

The operating-system identity is still the invoking user. Do not allowlist code you would not otherwise review and execute locally.

## Enable the Project Allowlist

Create an empty allowlist in an initialized project:

```bash
intentkit checker init --path ./my-project
```

This creates `.intent/external-checkers.json` with an empty `checkers` array. An empty allowlist is valid and runs no external code.

Use the same command surface to inspect loaded checkers:

```bash
intentkit checker list --path ./my-project
```

The list includes built-in checkers and any external checker whose allowlist entry, manifest, and entrypoint all validate. An invalid or stale external entry fails closed with a descriptive error; it is never silently ignored.

## Allowlist Contract

The project allowlist is JSON and belongs in version control:

```json
{
  "schema_version": "1",
  "checkers": [
    {
      "checker_id": "example.contract-check",
      "version": "1.0.0",
      "manifest": "tools/contract-check/intentkit-checker.json",
      "manifest_sha256": "sha256:replace-with-manifest-digest",
      "enabled": true
    }
  ]
}
```

The allowlist identity must exactly match the manifest identity. `enabled` must be `true`; an entry set to `false` is rejected rather than treated as a surprising partial configuration. To stop execution, remove the entry in a reviewed change.

## Manifest Contract

Each checker has a project-contained `intentkit-checker.json` manifest:

```json
{
  "protocol_version": 1,
  "checker_id": "example.contract-check",
  "version": "1.0.0",
  "display_name": "Example Contract Check",
  "supported_kinds": ["contract_json"],
  "needs_network": false,
  "entrypoint": "checker.py",
  "entrypoint_sha256": "sha256:replace-with-entrypoint-digest",
  "max_timeout_seconds": 30
}
```

Checker IDs use lowercase dotted names, versions use a semantic-version-like form, supported proof kinds are non-empty strings, and timeouts are limited to 1–300 seconds. The manifest and entrypoint must both resolve inside the project root. Network-capable manifests are not supported in this release.

When code changes, compute a new entrypoint digest, update the manifest, compute a new manifest digest, and then update the allowlist. This intentional three-file review makes the authorization change visible in Git.

```bash
sha256sum tools/contract-check/checker.py
sha256sum tools/contract-check/intentkit-checker.json
```

## JSON Subprocess Protocol

Intent Kit invokes the pinned entrypoint as:

```text
python -I /absolute/project/path/to/checker.py
```

The runner supplies one JSON request on standard input. The request includes `protocol_version`, a run identifier, a read-only obligation summary, and the user-supplied checker configuration. The checker must write exactly one JSON object to standard output and exit with code zero.

```json
{
  "state": "pass",
  "summary": "Contract assertions passed.",
  "details": "3 assertions evaluated.",
  "source": "tests/contract.json",
  "artifacts": [],
  "metrics": {"assertions": 3},
  "external_run_id": null
}
```

`state` must be one of `pass`, `fail`, `inconclusive`, `error`, or `skipped`. The core validates the result, creates immutable evidence, links it to the proof, applies the existing proof evaluation policy, saves the graph atomically, and rerenders Markdown. A checker should return `fail` for a negative finding and reserve `error` for its own execution or configuration failure.

## Shape and Run an External Proof

The proof obligation must declare a kind supported by the external manifest. A policy pack may still supply risk and evaluation defaults.

```bash
intentkit shape "Validate contract export" \
  --description "The export must satisfy the pinned contract check." \
  --outcome OUT-001 \
  --policy release-critical \
  --proof-checker-kind contract_json \
  --required-checker example.contract-check \
  --path ./my-project

intentkit check PRF-001 \
  --checker example.contract-check \
  --config '{"contract":"contracts/export.json"}' \
  --path ./my-project
```

The core only runs a checker when the selected checker is allowlisted and its `supported_kinds` include `proof_obligation.properties["checker_kind"]`. A mismatch becomes an immutable `skipped` observation rather than executable behavior.

## Reference Fixture

The Intent Kit repository includes [`examples/external-file-checker`](../examples/external-file-checker) as a deliberately small reference implementation. It validates a project-contained file and optional text assertion, emits a result through the protocol, and is pinned in the repository’s own `.intent/external-checkers.json` for self-hosted verification.

## Current Limits and Future Work

P3 intentionally supports only **project-local Python scripts** invoked through the JSON protocol. It does not load Python packages in-process, discover entry points, permit network access, run shell commands, install dependencies, sign manifests, execute containers, or evaluate evidence freshness automatically. P4 will focus on reviewed incremental Spec Kit synchronization; stronger process isolation and signed distribution are later hardening directions, not assurances made by this release.
