from pathlib import Path

import pytest

from intentkit.importers import SpecKitImporter
from intentkit.kernel import GraphStore, NodeStatus, RelationType
from intentkit.renderer import MarkdownRenderer


def write_speckit_feature(source: Path) -> dict[str, str]:
    source.mkdir()
    artifacts = {
        "spec.md": """# Feature Specification: Safe Checkout

**Input**: User description: "Prevent duplicate orders on retry."

## User Scenarios & Testing

### User Story 1 - Retry safely (Priority: P1)

A shopper can repeat a confirmation without creating another order.

**Why this priority**: Duplicate charges cause direct customer harm.

**Independent Test**: Repeat the same confirmation and verify one order exists.

**Acceptance Scenarios**:

1. **Given** a pending checkout, **When** the confirmation repeats, **Then** one order exists.

---

### User Story 2 - Explain retry state (Priority: P2)

A shopper can see whether a retry returned the original order.

**Why this priority**: Clear feedback reduces duplicate support requests.

**Independent Test**: Replay the request and inspect the returned order reference.

**Acceptance Scenarios**:

1. **Given** a prior confirmation, **When** it is replayed, **Then** the original reference returns.

## Requirements

### Functional Requirements

- **FR-001**: System MUST persist one idempotency key per checkout confirmation.
- **FR-002**: System MUST return the original order for a repeated confirmation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A repeated confirmation returns exactly one order.
""",
        "plan.md": """# Implementation Plan: Safe Checkout

## Summary

Persist provider idempotency keys and return the original order on replay.

## Technical Context

**Language/Version**: Python 3.11
**Testing**: pytest
""",
        "tasks.md": """# Tasks: Safe Checkout

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create configuration for checkout retries in src/checkout/config.py

## Phase 3: User Story 1 - Retry safely (Priority: P1)

- [x] T002 [P] [US1] Add retry contract test in tests/test_checkout.py

## Phase 4: User Story 2 - Explain retry state (Priority: P2)

- [ ] T003 [US2] Return original order reference in src/checkout/service.py
""",
    }
    for filename, content in artifacts.items():
        (source / filename).write_text(content, encoding="utf-8")
    return artifacts


def test_importer_maps_artifacts_with_provenance_and_preserves_sources(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    artifacts = write_speckit_feature(source)
    destination = tmp_path / "intent-project"
    store = GraphStore(destination)
    graph = store.initialize("Imported Checkout")

    report = SpecKitImporter(source).import_into(graph)
    store.save(graph)
    MarkdownRenderer(destination).render(graph)

    assert report.feature_outcome_id == "OUT-001"
    assert report.user_stories == 2
    assert report.functional_requirements == 2
    assert report.decisions == 1
    assert report.tasks == 3
    assert len(graph.nodes) == 9

    feature = graph.get_node("OUT-001")
    assert feature.properties["provenance"]["artifact"] == "spec.md"
    assert feature.properties["provenance"]["sha256"].startswith("sha256:")
    assert feature.properties["success_measures"] == [
        "A repeated confirmation returns exactly one order."
    ]

    completed_task = graph.get_node("TSK-002")
    assert completed_task.status == NodeStatus.VERIFIED.value
    assert completed_task.properties["source_identifier"] == "T002"
    task_links = graph.outgoing(completed_task.id, RelationType.IMPLEMENTS)
    assert [edge.target for edge in task_links] == ["REQ-001"]
    assert graph.get_node("REQ-001").properties["story_label"] == "US1"
    assert (destination / "intent" / "design.md").read_text(encoding="utf-8").find("T002") >= 0

    for filename, original in artifacts.items():
        assert (source / filename).read_text(encoding="utf-8") == original


def test_importer_rejects_duplicate_source_roots(tmp_path: Path) -> None:
    source = tmp_path / "speckit-feature"
    write_speckit_feature(source)
    graph = GraphStore(tmp_path / "intent-project").initialize("Imported Checkout")
    importer = SpecKitImporter(source)
    importer.import_into(graph)

    with pytest.raises(ValueError, match="already been imported"):
        importer.import_into(graph)


def test_importer_requires_a_spec_file(tmp_path: Path) -> None:
    source = tmp_path / "empty-feature"
    source.mkdir()

    with pytest.raises(FileNotFoundError, match="requires spec.md"):
        SpecKitImporter(source)
