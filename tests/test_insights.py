from pathlib import Path

from intentkit.insights import DriftStatus, analyze_impact, scan_drift, sha256_digest, source_nodes
from intentkit.kernel import IntentGraph, NodeStatus, NodeType, RelationType


def provenance(source: Path, artifact: str) -> dict[str, object]:
    digest = sha256_digest(source / artifact)
    return {
        "provenance": {
            "importer": "intentkit.speckit",
            "source_root": str(source),
            "artifact": artifact,
            "sha256": digest,
            "line": 1,
        }
    }


def imported_graph(source: Path) -> IntentGraph:
    graph = IntentGraph(project_name="Insight fixture")
    outcome = graph.add_node(
        NodeType.OUTCOME,
        "Imported feature",
        "Feature outcome.",
        properties=provenance(source, "spec.md"),
    )
    requirement = graph.add_node(
        NodeType.REQUIREMENT,
        "Imported requirement",
        "Requirement from an imported source.",
        properties=provenance(source, "spec.md"),
    )
    task = graph.add_node(
        NodeType.IMPLEMENTATION_TASK,
        "Imported task",
        "Task for the imported requirement.",
        status=NodeStatus.PLANNED,
        properties=provenance(source, "tasks.md"),
    )
    proof = graph.add_node(
        NodeType.PROOF_OBLIGATION,
        "Imported proof",
        "Proof obligation awaiting evidence.",
        status=NodeStatus.PLANNED,
    )
    evidence = graph.add_node(
        NodeType.EVIDENCE,
        "Recorded evidence",
        "Evidence attached to the proof.",
        status=NodeStatus.ACTIVE,
    )
    graph.add_edge(requirement.id, outcome.id, RelationType.DERIVES_FROM)
    graph.add_edge(task.id, requirement.id, RelationType.IMPLEMENTS)
    graph.add_edge(requirement.id, proof.id, RelationType.REQUIRES_PROOF)
    graph.add_edge(evidence.id, proof.id, RelationType.PROVES)
    return graph


def test_scan_drift_detects_unchanged_changed_missing_and_source_scope(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    source.mkdir()
    (source / "spec.md").write_text("feature specification\n", encoding="utf-8")
    (source / "tasks.md").write_text("task list\n", encoding="utf-8")
    graph = imported_graph(source)

    unchanged = scan_drift(graph)
    assert [(record.artifact, record.status, record.node_ids) for record in unchanged] == [
        ("spec.md", DriftStatus.UNCHANGED, ("OUT-001", "REQ-001")),
        ("tasks.md", DriftStatus.UNCHANGED, ("TSK-001",)),
    ]
    assert [record.artifact for record in scan_drift(graph, source / "spec.md")] == ["spec.md"]

    (source / "spec.md").write_text("changed feature specification\n", encoding="utf-8")
    (source / "tasks.md").unlink()
    drift = {record.artifact: record.status for record in scan_drift(graph)}
    assert drift == {"spec.md": DriftStatus.CHANGED, "tasks.md": DriftStatus.MISSING}


def test_impact_traverses_typed_paths_and_reports_unverified_proofs(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    source.mkdir()
    (source / "spec.md").write_text("feature specification\n", encoding="utf-8")
    (source / "tasks.md").write_text("task list\n", encoding="utf-8")
    graph = imported_graph(source)

    report = analyze_impact(graph, "REQ-001")

    assert [path.node.id for path in report.paths] == ["OUT-001", "PRF-001", "TSK-001", "EVD-001"]
    assert [node.id for node in report.proof_gaps] == ["PRF-001"]
    assert report.paths[2].hops[0].direction == "incoming"
    assert [node.id for node in source_nodes(graph, source / "spec.md")] == ["OUT-001", "REQ-001"]
