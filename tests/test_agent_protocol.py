import json
from pathlib import Path

from test_speckit_importer import write_speckit_feature

from intentkit.cli import main


def agent_request(root: Path, request: dict, capsys) -> tuple[int, dict]:
    status = main(["agent", "--path", str(root), "--request", json.dumps(request)])
    return status, json.loads(capsys.readouterr().out)


def test_agent_reads_machine_readable_project_state(tmp_path: Path, capsys) -> None:
    root = tmp_path / "agent-project"
    assert main(["init", "--path", str(root), "--project-name", "Agent Project"]) == 0
    assert (
        main(
            [
                "capture",
                "Agent visibility",
                "--description",
                "Agents can inspect Intent Kit through structured JSON.",
                "--path",
                str(root),
            ]
        )
        == 0
    )
    capsys.readouterr()

    status, payload = agent_request(
        root,
        {
            "protocol_version": 1,
            "request_id": "snapshot-1",
            "operation": "snapshot",
            "arguments": {"include_graph": True},
        },
        capsys,
    )

    assert status == 0
    assert payload["ok"] is True
    assert payload["applied"] is False
    assert payload["result"]["summary"]["project_name"] == "Agent Project"
    assert payload["result"]["graph"]["nodes"]["OUT-001"]["title"] == "Agent visibility"


def test_agent_returns_structured_policy_checker_and_impact_results(tmp_path: Path, capsys) -> None:
    root = tmp_path / "agent-project"
    assert main(["init", "--path", str(root)]) == 0
    assert (
        main(
            [
                "capture",
                "Agent use",
                "--description",
                "Support safe agent access.",
                "--path",
                str(root),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Expose protocol",
                "--description",
                "Provide structured project state.",
                "--outcome",
                "OUT-001",
                "--policy",
                "documentation",
                "--path",
                str(root),
            ]
        )
        == 0
    )
    capsys.readouterr()

    _, policies = agent_request(
        root,
        {
            "protocol_version": 1,
            "request_id": "policies-1",
            "operation": "policies",
            "arguments": {},
        },
        capsys,
    )
    assert {pack["name"] for pack in policies["result"]["packs"]} >= {"documentation", "migration"}

    _, checkers = agent_request(
        root,
        {
            "protocol_version": 1,
            "request_id": "checkers-1",
            "operation": "checkers",
            "arguments": {},
        },
        capsys,
    )
    assert checkers["result"]["checkers"][0]["checker_id"] == "local.file-exists"

    _, impact = agent_request(
        root,
        {
            "protocol_version": 1,
            "request_id": "impact-1",
            "operation": "impact",
            "arguments": {"node_id": "REQ-001"},
        },
        capsys,
    )
    assert impact["result"]["root"]["id"] == "REQ-001"
    assert any(path["node"]["id"] == "PRF-001" for path in impact["result"]["paths"])


def test_agent_reports_errors_and_requires_explicit_apply_for_mutation(
    tmp_path: Path, capsys
) -> None:
    root = tmp_path / "agent-project"
    assert main(["init", "--path", str(root)]) == 0
    capsys.readouterr()

    invalid_status = main(["agent", "--path", str(root), "--request", "not-json"])
    invalid = json.loads(capsys.readouterr().out)
    assert invalid_status == 2
    assert invalid["error"]["code"] == "invalid_json"

    request = {
        "protocol_version": 1,
        "request_id": "capture-1",
        "operation": "capture",
        "arguments": {
            "title": "No silent write",
            "description": "An agent must request explicit apply mode.",
        },
    }
    preview_status, preview = agent_request(root, request, capsys)
    assert preview_status == 0
    assert preview["applied"] is False
    assert preview["result"]["requires_apply"] is True

    apply_status = main(["agent", "--path", str(root), "--apply", "--request", json.dumps(request)])
    applied = json.loads(capsys.readouterr().out)
    assert apply_status == 0
    assert applied["applied"] is True
    assert applied["result"]["created"][0]["id"] == "OUT-001"


def test_agent_computer_workspace_write_requires_apply(tmp_path: Path, capsys) -> None:
    root = tmp_path / "agent-project"
    assert main(["init", "--path", str(root)]) == 0
    capsys.readouterr()
    request = {
        "protocol_version": 1,
        "request_id": "workspace-1",
        "operation": "computer.write_file",
        "arguments": {
            "session_id": "agent_1",
            "path": "research/summary.md",
            "content": "# Agent notes\n",
        },
    }

    _, preview = agent_request(root, request, capsys)
    assert preview["result"]["requires_apply"] is True
    assert not (root / ".intent" / "agent-workspace" / "agent_1").exists()

    apply_status = main(["agent", "--path", str(root), "--apply", "--request", json.dumps(request)])
    applied = json.loads(capsys.readouterr().out)
    assert apply_status == 0
    assert applied["applied"] is True
    target = root / ".intent" / "agent-workspace" / "agent_1" / "research" / "summary.md"
    assert target.read_text(encoding="utf-8") == "# Agent notes\n"


def test_agent_applies_shaping_and_approved_proof_check(tmp_path: Path, capsys) -> None:
    root = tmp_path / "agent-project"
    (root / "README.md").parent.mkdir(parents=True)
    (root / "README.md").write_text("agent proof\n", encoding="utf-8")
    assert main(["init", "--path", str(root)]) == 0
    capsys.readouterr()

    capture = {
        "protocol_version": 1,
        "request_id": "capture-proof-1",
        "operation": "capture",
        "arguments": {"title": "Agent proof", "description": "Agents can run approved checks."},
    }
    assert main(["agent", "--path", str(root), "--apply", "--request", json.dumps(capture)]) == 0
    capsys.readouterr()

    shape = {
        "protocol_version": 1,
        "request_id": "shape-proof-1",
        "operation": "shape",
        "arguments": {
            "title": "Verify artifact",
            "description": "The agent must verify the repository artifact.",
            "outcome_id": "OUT-001",
            "proof_title": "README exists",
            "proof_description": "README.md is available.",
            "proof_checker_kind": "file_exists",
        },
    }
    assert main(["agent", "--path", str(root), "--apply", "--request", json.dumps(shape)]) == 0
    capsys.readouterr()

    check = {
        "protocol_version": 1,
        "request_id": "check-proof-1",
        "operation": "check",
        "arguments": {
            "obligation_id": "PRF-001",
            "checker_id": "local.file-exists",
            "config": {"path": "README.md"},
        },
    }
    _, preview = agent_request(root, check, capsys)
    assert preview["result"]["requires_apply"] is True

    assert main(["agent", "--path", str(root), "--apply", "--request", json.dumps(check)]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["result"]["check"]["state"] == "pass"

    _, status = agent_request(
        root,
        {
            "protocol_version": 1,
            "request_id": "status-proof-1",
            "operation": "status",
            "arguments": {},
        },
        capsys,
    )
    assert status["result"]["proof_coverage"]["verified"] == 1


def test_agent_proposes_and_applies_reviewed_speckit_sync(tmp_path: Path, capsys) -> None:
    source = tmp_path / "speckit-feature"
    artifacts = write_speckit_feature(source)
    root = tmp_path / "agent-project"
    assert main(["init", "--path", str(root)]) == 0
    capsys.readouterr()
    assert main(["import-speckit", "--path", str(root), str(source)]) == 0
    capsys.readouterr()
    (source / "spec.md").write_text(
        artifacts["spec.md"].replace(
            "System MUST return the original order for a repeated confirmation.",
            "System MUST return the original audited order for a repeated confirmation.",
        ),
        encoding="utf-8",
    )
    proposal_request = {
        "protocol_version": 1,
        "request_id": "sync-proposal-001",
        "operation": "sync.propose",
        "arguments": {"source": str(source)},
    }
    _, proposal_response = agent_request(root, proposal_request, capsys)
    proposal = proposal_response["result"]["proposal"]
    changed = {delta["key"]: delta["action"] for delta in proposal["deltas"]}
    assert changed["functional:FR-002"] == "updated"

    apply_request = {
        "protocol_version": 1,
        "request_id": "sync-apply-001",
        "operation": "sync.apply",
        "arguments": {"source": str(source), "proposal": proposal},
    }
    _, preview = agent_request(root, apply_request, capsys)
    assert preview["applied"] is False
    assert preview["result"]["requires_apply"] is True

    assert (
        main(["agent", "--path", str(root), "--apply", "--request", json.dumps(apply_request)]) == 0
    )
    applied = json.loads(capsys.readouterr().out)
    assert applied["applied"] is True
    assert applied["result"]["sync"]["updated"] >= 1
