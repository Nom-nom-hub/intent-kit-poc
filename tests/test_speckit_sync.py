from pathlib import Path

import pytest
from test_speckit_importer import write_speckit_feature

from intentkit.importers import SpecKitImporter
from intentkit.importers.synchronizer import SpecKitSynchronizer, key_for_node
from intentkit.kernel import GraphStore, NodeStatus
from intentkit.renderer import MarkdownRenderer


def import_feature(source: Path, destination: Path) -> GraphStore:
    store = GraphStore(destination)
    graph = store.initialize("Imported Checkout")
    SpecKitImporter(source).import_into(graph)
    store.save(graph)
    MarkdownRenderer(destination).render(graph)
    return store


def source_nodes_by_key(store: GraphStore) -> dict[str, str]:
    return {
        key: node.id
        for node in store.load().nodes.values()
        if (key := key_for_node(node)) is not None
    }


def test_sync_proposes_and_applies_reviewed_source_changes_with_stable_ids(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    original = write_speckit_feature(source)
    store = import_feature(source, tmp_path / "intent-project")
    synchronizer = SpecKitSynchronizer(source)
    initial = synchronizer.propose(store.load())
    assert initial.change_count == 0
    assert {delta.action for delta in initial.deltas} == {"unchanged"}

    before_ids = source_nodes_by_key(store)
    changed_spec = original["spec.md"].replace(
        "System MUST persist one idempotency key per checkout confirmation.",
        "System MUST persist a durable idempotency key per checkout confirmation.",
    )
    changed_spec = changed_spec.replace(
        "- **FR-002**: System MUST return the original order for a repeated confirmation.\n",
        "- **FR-002**: System MUST return the original order for a repeated confirmation.\n"
        "- **FR-003**: System MUST audit duplicate confirmation attempts.\n",
    )
    changed_tasks = original["tasks.md"].replace(
        "- [ ] T003 [US2] Return original order reference in src/checkout/service.py",
        "- [x] T003 [US2] Return original order reference in src/checkout/service.py",
    )
    removed_setup_task = (
        "- [ ] T001 Create configuration for checkout retries in src/checkout/config.py\n\n"
    )
    changed_tasks = changed_tasks.replace(removed_setup_task, "")
    (source / "spec.md").write_text(changed_spec, encoding="utf-8")
    (source / "tasks.md").write_text(changed_tasks, encoding="utf-8")

    proposal = synchronizer.propose(store.load())
    actions = {delta.key: delta.action for delta in proposal.deltas}
    assert actions["functional:FR-001"] == "updated"
    assert actions["functional:FR-003"] == "added"
    assert actions["task:T001"] == "removed"
    assert actions["task:T003"] == "updated"
    assert before_ids["functional:FR-001"] in proposal.impacted_node_ids
    proposal_path = synchronizer.write_proposal(store, proposal)
    assert proposal_path.is_file()
    assert (source / "spec.md").read_text(encoding="utf-8") == changed_spec
    assert (source / "tasks.md").read_text(encoding="utf-8") == changed_tasks

    report = synchronizer.apply(store, proposal)
    graph = store.load()
    after_ids = source_nodes_by_key(store)
    assert report.updated >= 2
    assert report.added == 1
    assert report.removed == 1
    assert after_ids["functional:FR-001"] == before_ids["functional:FR-001"]
    assert "task:T001" not in after_ids
    assert graph.get_node(after_ids["task:T003"]).status == NodeStatus.VERIFIED.value
    assert "durable idempotency" in graph.get_node(after_ids["functional:FR-001"]).description
    assert report.record_path.is_file()
    assert (store.project_root / "intent" / "design.md").is_file()

    with pytest.raises(ValueError, match="stale"):
        synchronizer.apply(store, proposal)


def test_sync_rejects_proposal_when_source_changes_after_review(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    original = write_speckit_feature(source)
    store = import_feature(source, tmp_path / "intent-project")
    synchronizer = SpecKitSynchronizer(source)
    proposal = synchronizer.propose(store.load())

    (source / "spec.md").write_text(
        original["spec.md"].replace("Safe Checkout", "Changed Checkout", 1), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="stale"):
        synchronizer.apply(store, proposal)


def test_sync_requires_a_previously_imported_source_root(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    write_speckit_feature(source)
    graph = GraphStore(tmp_path / "intent-project").initialize("Empty Project")

    with pytest.raises(ValueError, match="not imported"):
        SpecKitSynchronizer(source).propose(graph)
