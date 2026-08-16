# Policy Packs

Policy Packs provide **risk-calibrated defaults** for Intent Kit. They keep the command workflow short while making the review and proof expectations for common work visible in the graph and generated Markdown.

A pack is a local, declarative JSON contract. It does not run code, discover plug-ins, execute checkers, or contact a service. Applying a pack only supplies defaults when a user shapes a requirement.

## Shipped Packs

| Pack | Risk | Proof evaluation | Main expectation |
|---|---:|---|---|
| `release-critical` | `R3` | `all` | Create a proof obligation, require explicit review or automated-validation evidence, and refresh evidence within 7 days after related change. |
| `migration` | `R2` | `manual` | Create a proof obligation, preserve source provenance or a reviewed migration record, and refresh evidence within 30 days after change. |
| `documentation` | `R1` | `latest` | Create a focused proof obligation and refresh its current review evidence within 90 days after change. |

These packs are built into Intent Kit and cannot be overridden by a project file. That makes a pack name stable across repositories and prevents a local configuration from silently weakening a well-known policy.

## Discover and Inspect Packs

```bash
# List shipped packs and any local packs in .intent/policies.json.
intentkit policy list --path ./my-project

# Inspect one pack before using it.
intentkit policy show release-critical --path ./my-project

# Create a commented example JSON policy configuration for new team-specific packs.
intentkit policy init --path ./my-project
```

`policy init` writes `.intent/policies.json` only when that file does not already exist. It never rewrites an existing project policy file.

## Apply a Pack While Shaping

```bash
intentkit shape "Protect release quality" \
  --description "A release-critical change must have current validation evidence." \
  --outcome OUT-001 \
  --policy release-critical \
  --path ./my-project
```

The command above creates a requirement plus an automatically generated proof obligation. It records the exact applied pack metadata on both nodes, including the pack name, risk, evaluation policy, freshness expectation, and review/provenance expectation. `intentkit status` summarizes pack use, while generated `intent/intent.md` and `intent/evidence.md` show the applied policy next to the affected work.

### Precedence

Policy Packs are defaults, not hidden overrides. Intent Kit uses the following order for shaping options:

| Setting | Precedence order |
|---|---|
| Risk | Explicit `--risk` → selected pack risk → historical `R1` default |
| Proof evaluation | Explicit `--proof-evaluation` → selected pack evaluation → historical `latest` default |
| Required checker identities | Explicit repeatable `--required-checker` → selected pack checker list → no checker requirement |
| Proof title and description | Explicit `--proof-title` and `--proof-description` → generated when the selected pack requires a proof → no proof for legacy shaping without a pack |

An explicit `--proof-title` still requires a paired `--proof-description`. A pack only generates proof text when both were omitted. This preserves the existing CLI contract while making a high-risk workflow concise.

## Local Team Packs

Projects may add policy names in `.intent/policies.json`. The file is intentionally JSON-only and version-controlled. A minimal example is:

```json
{
  "schema_version": "1",
  "packs": [
    {
      "name": "team-review",
      "title": "Team Review",
      "description": "Important changes require a recorded review.",
      "risk": "R2",
      "evaluation": "manual",
      "proof_required": true,
      "evidence_freshness_days": 30,
      "review_required": true,
      "source_provenance_required": false,
      "required_checkers": []
    }
  ]
}
```

A local pack name must be 2–64 lowercase letters, digits, and hyphens. It must define a known risk class (`R0`–`R3`), one supported proof evaluation (`latest`, `all`, `any`, or `manual`), a boolean `proof_required` flag, and valid optional freshness/checker settings. Invalid files fail closed with a clear CLI error; Intent Kit never guesses an unvalidated policy.

## Review and Evidence Lifecycle

A pack does not automatically verify anything. It makes the expected proof visible and creates an obligation when required. Use `intentkit check` for trusted local checker evidence or `intentkit prove` for a review, CI run, or other explicit observation. Graph Insight can then show the related proof in `intentkit impact` output.

The freshness value is an expectation recorded on the policy metadata in this increment. Automatic evidence-age enforcement will be added with the next policy enforcement work; it is not silently inferred from timestamps today.

## Security Boundary

Policy Packs are deliberately non-executable. A JSON policy can set checker **identity** requirements, but it cannot load a package, supply a command, or bypass the registered-checker boundary. Controlled external checker discovery and isolation remains a later roadmap milestone.
