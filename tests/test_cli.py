from pathlib import Path

from test_speckit_importer import write_speckit_feature

from intentkit.cli import main
from intentkit.kernel import GraphStore, NodeStatus


def test_cli_end_to_end_workflow(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    assert main(["init", "--path", root, "--project-name", "Checkout Safety"]) == 0
    assert (
        main(
            [
                "capture",
                "Prevent duplicate orders",
                "--path",
                root,
                "--description",
                "Retries must not create duplicate orders.",
                "--success-measure",
                "A repeated confirmation returns one order.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Use idempotency keys",
                "--path",
                root,
                "--description",
                "Every confirmation request must carry an idempotency key.",
                "--outcome",
                "OUT-001",
                "--risk",
                "R3",
                "--decision-title",
                "Use provider idempotency keys",
                "--rationale",
                "Provider-backed idempotency is safest.",
                "--alternative",
                "Time-window deduplication",
                "--proof-title",
                "Prove retries are safe",
                "--proof-description",
                "A repeated confirmation returns exactly one order.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "prove",
                "PRF-001",
                "Payment contract test",
                "--path",
                root,
                "--description",
                "The retry contract passed against the payment sandbox.",
                "--source",
                "tests/test_payment_contract.py",
                "--result",
                "pass",
            ]
        )
        == 0
    )
    assert main(["status", "--path", root]) == 0

    graph = GraphStore(tmp_path).load()
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    assert (tmp_path / "intent" / "intent.md").exists()
    assert "Payment contract test" in (tmp_path / "intent" / "evidence.md").read_text()
    assert "Proof coverage: 1/1 verified" in capsys.readouterr().out


def test_cli_runs_a_checker_backed_proof(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    (tmp_path / "release-marker.txt").write_text("ready\n", encoding="utf-8")
    assert main(["init", "--path", root, "--project-name", "Checker CLI"]) == 0
    assert (
        main(
            [
                "capture",
                "Ship a proof-backed release",
                "--path",
                root,
                "--description",
                "The release must include the required marker.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Require the release marker",
                "--path",
                root,
                "--description",
                "The release marker must be present in the project.",
                "--outcome",
                "OUT-001",
                "--proof-title",
                "Check the release marker",
                "--proof-description",
                "release-marker.txt must exist.",
                "--proof-checker-kind",
                "file_exists",
                "--proof-evaluation",
                "all",
                "--required-checker",
                "local.file-exists",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "check",
                "PRF-001",
                "--path",
                root,
                "--checker",
                "local.file-exists",
                "--config",
                '{"path":"release-marker.txt"}',
            ]
        )
        == 0
    )

    graph = GraphStore(tmp_path).load()
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    assert graph.get_node("EVD-001").properties["checker"]["id"] == "local.file-exists"
    assert "PASS: Required path is present" in capsys.readouterr().out


def test_cli_imports_a_speckit_feature(tmp_path: Path, capsys) -> None:
    source = tmp_path / "speckit-feature"
    source.mkdir()
    (source / "spec.md").write_text(
        """# Feature Specification: Retry Safety

**Input**: User description: "Avoid duplicate orders."

## User Scenarios & Testing

### User Story 1 - Retry once (Priority: P1)

A shopper can safely repeat checkout confirmation.

**Why this priority**: Duplicate charges harm customers.

**Independent Test**: Repeat confirmation and verify one order.

**Acceptance Scenarios**:

1. **Given** a pending checkout, **When** confirmation repeats, **Then** one order exists.

## Requirements

### Functional Requirements

- **FR-001**: System MUST store one idempotency key per confirmation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Repeated confirmation returns one order.
""",
        encoding="utf-8",
    )
    (source / "tasks.md").write_text(
        """# Tasks: Retry Safety

## Phase 3: User Story 1 - Retry once (Priority: P1)

- [ ] T001 [US1] Add idempotency support in src/checkout.py
""",
        encoding="utf-8",
    )
    root = str(tmp_path / "intent-project")
    assert main(["init", "--path", root, "--project-name", "Imported CLI"]) == 0

    assert main(["import-speckit", str(source), "--path", root]) == 0

    graph = GraphStore(Path(root)).load()
    assert graph.get_node("OUT-001").properties["provenance"]["importer"] == "intentkit.speckit"
    assert graph.get_node("TSK-001").properties["source_identifier"] == "T001"
    assert "Imported Spec Kit feature into OUT-001" in capsys.readouterr().out


def test_cli_reports_import_drift_and_requirement_impact(tmp_path: Path, capsys) -> None:
    source = tmp_path / "speckit-feature"
    source.mkdir()
    spec = source / "spec.md"
    spec.write_text(
        """# Feature Specification: Retry Safety

**Input**: User description: "Avoid duplicate orders."

## User Scenarios & Testing

### User Story 1 - Retry once (Priority: P1)

A shopper can safely repeat checkout confirmation.

**Why this priority**: Duplicate charges harm customers.

**Independent Test**: Repeat confirmation and verify one order.

**Acceptance Scenarios**:

1. **Given** a pending checkout, **When** confirmation repeats, **Then** one order exists.

## Requirements

### Functional Requirements

- **FR-001**: System MUST store one idempotency key per confirmation.
""",
        encoding="utf-8",
    )
    root = str(tmp_path / "intent-project")
    assert main(["init", "--path", root, "--project-name", "Insight CLI"]) == 0
    assert main(["import-speckit", str(source), "--path", root]) == 0
    assert main(["drift", "--path", root]) == 0
    assert "1 unchanged" in capsys.readouterr().out

    changed = spec.read_text(encoding="utf-8") + "\nChanged after import.\n"
    spec.write_text(changed, encoding="utf-8")
    assert main(["drift", "--path", root]) == 1
    assert "CHANGED:" in capsys.readouterr().out
    assert main(["impact", "REQ-001", "--path", root]) == 0
    impact_output = capsys.readouterr().out
    assert "Impact root: REQ-001" in impact_output
    assert "OUT-001" in impact_output


def test_cli_policy_pack_shapes_release_critical_defaults(tmp_path: Path, capsys) -> None:
    root = str(tmp_path / "policy-project")

    assert main(["policy", "list", "--path", root]) == 0
    assert "release-critical" in capsys.readouterr().out
    assert main(["init", "--path", root, "--project-name", "Policy CLI"]) == 0
    assert (
        main(
            [
                "capture",
                "Ship safely",
                "--description",
                "Make releases reviewable.",
                "--path",
                root,
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Protect release quality",
                "--description",
                "Every release-critical change needs current proof.",
                "--outcome",
                "OUT-001",
                "--policy",
                "release-critical",
                "--path",
                root,
            ]
        )
        == 0
    )

    graph = GraphStore(Path(root)).load()
    requirement = graph.get_node("REQ-001")
    proof = graph.get_node("PRF-001")
    assert requirement.properties["risk"] == "R3"
    assert requirement.properties["policy_pack"]["name"] == "release-critical"
    assert proof.title == "Verify Protect release quality"
    assert proof.properties["evaluation"] == "all"
    assert proof.properties["policy_pack"]["evidence_freshness_days"] == 7
    assert (
        main(
            [
                "prove",
                "PRF-001",
                "Policy review",
                "--description",
                "Release owner reviewed the validation evidence.",
                "--source",
                "review:release-owner",
                "--result",
                "pass",
                "--path",
                root,
            ]
        )
        == 0
    )
    assert GraphStore(Path(root)).load().get_node("PRF-001").status == NodeStatus.VERIFIED.value

    assert main(["status", "--path", root]) == 0
    assert "Policy packs: release-critical: 1" in capsys.readouterr().out


def test_cli_proposes_and_applies_reviewed_speckit_sync(tmp_path: Path, capsys) -> None:
    source = tmp_path / "speckit-feature"
    artifacts = write_speckit_feature(source)
    root = tmp_path / "intent-project"
    assert main(["init", "--path", str(root), "--project-name", "Sync CLI"]) == 0
    capsys.readouterr()
    assert main(["import-speckit", str(source), "--path", str(root)]) == 0
    capsys.readouterr()
    initial_graph = GraphStore(root).load()
    initial_requirement_id = next(
        node.id
        for node in initial_graph.nodes.values()
        if node.properties.get("source_identifier") == "FR-001"
    )
    changed_spec = artifacts["spec.md"].replace(
        "System MUST persist one idempotency key per checkout confirmation.",
        "System MUST persist a durable idempotency key per checkout confirmation.",
    )
    (source / "spec.md").write_text(changed_spec, encoding="utf-8")

    assert main(["sync-speckit", str(source), "--path", str(root)]) == 0
    proposal_output = capsys.readouterr().out
    assert "Proposed sync-" in proposal_output
    proposals = list((root / ".intent" / "sync-proposals").glob("sync-*.json"))
    assert len(proposals) == 1
    assert (
        main(
            [
                "sync-speckit",
                str(source),
                "--path",
                str(root),
                "--proposal",
                str(proposals[0]),
                "--apply",
            ]
        )
        == 0
    )

    graph = GraphStore(root).load()
    refreshed = graph.get_node(initial_requirement_id)
    assert "durable idempotency" in refreshed.description
    assert refreshed.properties["provenance"]["sha256"].startswith("sha256:")
    assert list((root / ".intent" / "sync-proposals").glob("*.applied.json"))
    assert "Applied sync-" in capsys.readouterr().out
