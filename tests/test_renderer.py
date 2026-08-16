from pathlib import Path

from intentkit.kernel import GraphStore, NodeStatus, NodeType, RelationType
from intentkit.renderer import MANUAL_END, MANUAL_START, MarkdownRenderer


def test_renderer_creates_linked_markdown_views(tmp_path: Path) -> None:
    store = GraphStore(tmp_path)
    graph = store.initialize("Checkout Safety")
    outcome = graph.add_node(NodeType.OUTCOME, "Prevent duplicate orders", "Checkout retries must be safe.")
    requirement = graph.add_node(NodeType.REQUIREMENT, "Use idempotency keys", "The retry must not create a duplicate order.")
    decision = graph.add_node(
        NodeType.DECISION,
        "Use provider idempotency keys",
        "Provider-supported idempotency is the safest available approach.",
        status=NodeStatus.PROPOSED,
        properties={"alternatives": ["time-window deduplication"]},
    )
    proof = graph.add_node(NodeType.PROOF_OBLIGATION, "Prove a retry is safe", "A repeated confirmation must return one order.")
    evidence = graph.add_node(
        NodeType.EVIDENCE,
        "Contract test passes",
        "The payment contract test passed.",
        status=NodeStatus.VERIFIED,
        properties={"result": "pass", "source": "tests/test_checkout.py"},
    )
    graph.add_edge(requirement.id, outcome.id, RelationType.DERIVES_FROM)
    graph.add_edge(decision.id, requirement.id, RelationType.ADDRESSES)
    graph.add_edge(requirement.id, proof.id, RelationType.REQUIRES_PROOF)
    graph.add_edge(evidence.id, proof.id, RelationType.PROVES)
    store.save(graph)

    paths = MarkdownRenderer(tmp_path).render(graph)
    assert {path.name for path in paths} == {"intent.md", "design.md", "evidence.md", "traceability.md"}
    assert "REQ-001 — Use idempotency keys" in (tmp_path / "intent" / "intent.md").read_text()
    assert "time-window deduplication" in (tmp_path / "intent" / "design.md").read_text()
    assert "Contract test passes" in (tmp_path / "intent" / "evidence.md").read_text()
    assert "`proves`" in (tmp_path / "intent" / "traceability.md").read_text()


def test_renderer_preserves_manual_notes(tmp_path: Path) -> None:
    store = GraphStore(tmp_path)
    graph = store.initialize("Notes")
    graph.add_node(NodeType.OUTCOME, "Keep notes", "Manual notes must persist.")
    store.save(graph)
    renderer = MarkdownRenderer(tmp_path)
    renderer.render(graph)

    intent_path = tmp_path / "intent" / "intent.md"
    content = intent_path.read_text()
    intent_path.write_text(
        content.replace(
            "Add team context, review notes, or links here. This section is preserved on re-render.",
            "Reviewed by the platform team on 2026-08-16.",
        )
    )
    renderer.render(graph)

    refreshed = intent_path.read_text()
    assert MANUAL_START in refreshed
    assert MANUAL_END in refreshed
    assert "Reviewed by the platform team on 2026-08-16." in refreshed
