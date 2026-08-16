from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from intentkit.kernel import GraphStore, NodeStatus, NodeType, RelationType
from intentkit.proof_checkers.builtin import FileExistsChecker
from intentkit.proof_checkers.models import CheckerDescriptor, CheckRequest, CheckResult, CheckState
from intentkit.proof_checkers.registry import CheckerRegistry
from intentkit.proof_checkers.runner import ProofRunner, aggregate_obligation_status


@dataclass
class StaticChecker:
    checker_id: str
    state: CheckState

    @property
    def descriptor(self) -> CheckerDescriptor:
        return CheckerDescriptor(
            checker_id=self.checker_id,
            version="1.0.0",
            display_name=self.checker_id,
        )

    def can_check(self, request: CheckRequest) -> bool:
        return True

    def run(self, request: CheckRequest) -> CheckResult:
        return CheckResult(
            state=self.state,
            summary=f"{self.checker_id} returned {self.state.value}.",
            source=f"checker:{self.checker_id}",
        )


def initialized_proof(tmp_path: Path, *, properties: dict | None = None) -> GraphStore:
    store = GraphStore(tmp_path)
    graph = store.initialize("Proof Checks")
    graph.add_node(
        NodeType.PROOF_OBLIGATION,
        "Required proof",
        "The project must satisfy the required proof.",
        status=NodeStatus.PLANNED,
        properties=properties or {},
    )
    store.save(graph)
    return store


def test_runner_records_evidence_and_renders_a_passing_file_check(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Checked\n", encoding="utf-8")
    store = initialized_proof(tmp_path, properties={"checker_kind": "file_exists"})
    registry = CheckerRegistry()
    registry.register(FileExistsChecker())

    result = ProofRunner(store, registry).run("PRF-001", "local.file-exists", {"path": "README.md"})

    graph = store.load()
    evidence = graph.get_node("EVD-001")
    assert result.state is CheckState.PASS
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    assert evidence.properties["result"] == "pass"
    assert evidence.properties["checker"] == {"id": "local.file-exists", "version": "1.0.0"}
    assert evidence.properties["run"]["config_fingerprint"].startswith("sha256:")
    assert graph.incoming("PRF-001", RelationType.PROVES)[0].source == "EVD-001"
    assert "Required path is present" in (tmp_path / "intent" / "evidence.md").read_text(
        encoding="utf-8"
    )


def test_file_checker_rejects_paths_outside_project(tmp_path: Path) -> None:
    store = initialized_proof(tmp_path, properties={"checker_kind": "file_exists"})
    registry = CheckerRegistry()
    registry.register(FileExistsChecker())

    result = ProofRunner(store, registry).run(
        "PRF-001", "local.file-exists", {"path": "../outside.txt"}
    )

    graph = store.load()
    assert result.state is CheckState.ERROR
    assert graph.get_node("PRF-001").status == NodeStatus.ACTIVE.value
    assert graph.get_node("EVD-001").properties["result"] == "error"


def test_all_policy_requires_every_configured_checker_and_tracks_latest_results(
    tmp_path: Path,
) -> None:
    store = initialized_proof(
        tmp_path,
        properties={
            "evaluation": "all",
            "required_checkers": ["local.alpha", "local.beta"],
        },
    )
    registry = CheckerRegistry()
    registry.register(StaticChecker("local.alpha", CheckState.PASS))
    registry.register(StaticChecker("local.beta", CheckState.PASS))
    runner = ProofRunner(store, registry)

    runner.run("PRF-001", "local.alpha")
    assert store.load().get_node("PRF-001").status == NodeStatus.ACTIVE.value

    runner.run("PRF-001", "local.beta")
    assert store.load().get_node("PRF-001").status == NodeStatus.VERIFIED.value

    registry = CheckerRegistry()
    registry.register(StaticChecker("local.alpha", CheckState.FAIL))
    registry.register(StaticChecker("local.beta", CheckState.PASS))
    ProofRunner(store, registry).run("PRF-001", "local.alpha")
    assert store.load().get_node("PRF-001").status == NodeStatus.FAILED.value


def test_all_policy_ignores_skipped_but_requires_a_real_pass(tmp_path: Path) -> None:
    store = initialized_proof(tmp_path, properties={"evaluation": "all", "required_checkers": []})
    graph = store.load()
    skipped = graph.add_node(
        NodeType.EVIDENCE,
        "Skipped checker",
        "Checker did not apply.",
        status=NodeStatus.ACTIVE,
        properties={"result": CheckState.SKIPPED.value},
    )
    graph.add_edge(skipped.id, "PRF-001", RelationType.PROVES)
    assert aggregate_obligation_status(graph, "PRF-001") == NodeStatus.ACTIVE

    passed = graph.add_node(
        NodeType.EVIDENCE,
        "Manual review",
        "Reviewer confirmed the proof.",
        status=NodeStatus.VERIFIED,
        properties={"result": CheckState.PASS.value},
    )
    graph.add_edge(passed.id, "PRF-001", RelationType.PROVES)
    assert aggregate_obligation_status(graph, "PRF-001") == NodeStatus.VERIFIED


def test_registry_rejects_duplicate_checker_ids() -> None:
    registry = CheckerRegistry()
    registry.register(StaticChecker("local.duplicate", CheckState.PASS))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(StaticChecker("local.duplicate", CheckState.FAIL))
