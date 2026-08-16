from pathlib import Path

import pytest

from intentkit.kernel import GraphStore, NodeStatus, NodeType, RelationType


def test_graph_store_creates_stable_ids_and_persists(tmp_path: Path) -> None:
    store = GraphStore(tmp_path)
    graph = store.initialize("Checkout Safety")
    outcome = graph.add_node(NodeType.OUTCOME, "Prevent duplicate orders", "Retries must not create duplicates.")
    requirement = graph.add_node(NodeType.REQUIREMENT, "Require idempotency", "Every confirmation request has an idempotency key.")
    graph.add_edge(requirement.id, outcome.id, RelationType.DERIVES_FROM)
    store.save(graph)

    loaded = store.load()
    assert outcome.id == "OUT-001"
    assert requirement.id == "REQ-001"
    assert loaded.nodes[requirement.id].title == "Require idempotency"
    assert loaded.outgoing(requirement.id)[0].relation == RelationType.DERIVES_FROM.value


def test_graph_rejects_invalid_edges(tmp_path: Path) -> None:
    graph = GraphStore(tmp_path).initialize("Invalid Edge")
    outcome = graph.add_node(NodeType.OUTCOME, "Protect users", "A safe outcome.")

    with pytest.raises(ValueError, match="Unknown target node"):
        graph.add_edge(outcome.id, "REQ-999", RelationType.DERIVES_FROM)

    with pytest.raises(ValueError, match="Self-referential"):
        graph.add_edge(outcome.id, outcome.id, RelationType.DERIVES_FROM)


def test_status_updates_are_saved(tmp_path: Path) -> None:
    store = GraphStore(tmp_path)
    graph = store.initialize("Status Test")
    proof = graph.add_node(NodeType.PROOF_OBLIGATION, "Run contract test", "The contract test must pass.")
    graph.set_status(proof.id, NodeStatus.VERIFIED)
    store.save(graph)

    assert store.load().get_node(proof.id).status == NodeStatus.VERIFIED.value
