import hashlib
import json
from pathlib import Path

import pytest

from intentkit.cli import main
from intentkit.kernel import GraphStore, NodeStatus, NodeType
from intentkit.proof_checkers.external import ExternalCheckerRegistry
from intentkit.proof_checkers.registry import CheckerRegistry
from intentkit.proof_checkers.runner import ProofRunner


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def create_allowed_checker(project: Path, *, manifest_digest: str | None = None) -> Path:
    checker_dir = project / "tools" / "example-checker"
    checker_dir.mkdir(parents=True)
    entrypoint = checker_dir / "checker.py"
    entrypoint.write_text(
        """import json
import sys

request = json.loads(sys.stdin.read())
assert request["protocol_version"] == 1
print(json.dumps({
    "state": "pass",
    "summary": "External protocol check passed.",
    "source": "external:example.protocol",
    "metrics": {"protocol": 1},
}))
""",
        encoding="utf-8",
    )
    manifest = checker_dir / "intentkit-checker.json"
    manifest.write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "checker_id": "example.protocol",
                "version": "1.0.0",
                "display_name": "Example Protocol Checker",
                "supported_kinds": ["external_json"],
                "needs_network": False,
                "entrypoint": "checker.py",
                "entrypoint_sha256": digest(entrypoint),
                "max_timeout_seconds": 10,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    intent_dir = project / ".intent"
    intent_dir.mkdir(exist_ok=True)
    (intent_dir / "external-checkers.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "checkers": [
                    {
                        "checker_id": "example.protocol",
                        "version": "1.0.0",
                        "manifest": "tools/example-checker/intentkit-checker.json",
                        "manifest_sha256": manifest_digest or digest(manifest),
                        "enabled": True,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def initialized_external_proof(project: Path) -> GraphStore:
    store = GraphStore(project)
    graph = store.initialize("External checks")
    graph.add_node(
        NodeType.PROOF_OBLIGATION,
        "External proof",
        "The external checker must return a typed result.",
        status=NodeStatus.PLANNED,
        properties={"checker_kind": "external_json"},
    )
    store.save(graph)
    return store


def test_allowed_pinned_external_checker_runs_through_proof_runner(tmp_path: Path) -> None:
    store = initialized_external_proof(tmp_path)
    create_allowed_checker(tmp_path)
    registry = CheckerRegistry()
    for checker in ExternalCheckerRegistry(tmp_path).load():
        registry.register(checker)

    result = ProofRunner(store, registry).run("PRF-001", "example.protocol")

    graph = store.load()
    assert result.state.value == "pass"
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    evidence = graph.get_node("EVD-001")
    assert evidence.properties["checker"] == {"id": "example.protocol", "version": "1.0.0"}
    assert evidence.properties["source"] == "external:example.protocol"


def test_entrypoint_modified_after_load_is_rejected_before_execution(tmp_path: Path) -> None:
    store = initialized_external_proof(tmp_path)
    manifest = create_allowed_checker(tmp_path)
    checker = ExternalCheckerRegistry(tmp_path).load()[0]
    (manifest.parent / "checker.py").write_text("print('mutated')\n", encoding="utf-8")
    registry = CheckerRegistry()
    registry.register(checker)

    result = ProofRunner(store, registry).run("PRF-001", "example.protocol")

    assert result.state.value == "error"
    assert "changed after authorization" in result.summary
    assert store.load().get_node("PRF-001").status == NodeStatus.ACTIVE.value


def test_manifest_digest_mismatch_blocks_external_checker_before_execution(tmp_path: Path) -> None:
    create_allowed_checker(tmp_path, manifest_digest="sha256:" + "0" * 64)

    with pytest.raises(ValueError, match="digest mismatch"):
        ExternalCheckerRegistry(tmp_path).load()


def test_modified_entrypoint_is_rejected_by_manifest_pin(tmp_path: Path) -> None:
    manifest = create_allowed_checker(tmp_path)
    entrypoint = manifest.parent / "checker.py"
    entrypoint.write_text("print('{}')\n", encoding="utf-8")

    with pytest.raises(ValueError, match="entrypoint digest mismatch"):
        ExternalCheckerRegistry(tmp_path).load()


def test_cli_checker_management_and_allowlisted_execution(tmp_path: Path, capsys) -> None:
    empty_project = tmp_path / "empty"
    assert main(["checker", "init", "--path", str(empty_project)]) == 0
    allowlist = empty_project / ".intent" / "external-checkers.json"
    assert json.loads(allowlist.read_text(encoding="utf-8"))["checkers"] == []
    assert main(["checker", "list", "--path", str(empty_project)]) == 0
    assert "local.file-exists@1.0.0 [built-in]" in capsys.readouterr().out

    project = tmp_path / "cli-external"
    initialized_external_proof(project)
    create_allowed_checker(project)
    assert main(["checker", "list", "--path", str(project)]) == 0
    assert "example.protocol@1.0.0 [external]" in capsys.readouterr().out
    assert (
        main(
            [
                "check",
                "PRF-001",
                "--checker",
                "example.protocol",
                "--config",
                "{}",
                "--path",
                str(project),
            ]
        )
        == 0
    )
    assert GraphStore(project).load().get_node("PRF-001").status == NodeStatus.VERIFIED.value


def test_disabled_entries_fail_closed(tmp_path: Path) -> None:
    create_allowed_checker(tmp_path)
    allowlist = tmp_path / ".intent" / "external-checkers.json"
    payload = json.loads(allowlist.read_text(encoding="utf-8"))
    payload["checkers"][0]["enabled"] = False
    allowlist.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Disabled external checkers"):
        ExternalCheckerRegistry(tmp_path).load()
