import json
import sys
from pathlib import Path

import pytest

from intentkit.agent_computer import COMMANDS, AgentComputer, AgentComputerError


def test_agent_computer_reads_project_and_excludes_own_workspace(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Agent Computer\n", encoding="utf-8")
    computer = AgentComputer(tmp_path)
    computer.write_workspace_file("agent-1", "notes.txt", "private agent scratch")

    listing = computer.list_project_files()
    paths = {entry["path"] for entry in listing["files"]}
    read = computer.read_project_file("README.md")

    assert "README.md" in paths
    assert not any("agent-workspace" in path for path in paths)
    assert read["content"] == "Agent Computer\n"
    assert read["sha256"].startswith("sha256:")


def test_agent_computer_writes_only_inside_agent_workspace_and_audits(tmp_path: Path) -> None:
    computer = AgentComputer(tmp_path)
    record = computer.write_workspace_file("agent_1", "reports/result.json", "{}")
    written = tmp_path / ".intent" / "agent-workspace" / "agent_1" / "reports" / "result.json"
    audit = tmp_path / ".intent" / "agent-computer-log.jsonl"

    assert written.read_text(encoding="utf-8") == "{}"
    assert record["path"] == ".intent/agent-workspace/agent_1/reports/result.json"
    audit_record = json.loads(audit.read_text(encoding="utf-8").strip())
    assert audit_record["action"] == "computer.write_file"

    with pytest.raises(AgentComputerError, match="remain inside"):
        computer.write_workspace_file("agent_1", "../../README.md", "blocked")


def test_agent_computer_runs_only_named_commands_and_records_output(
    tmp_path: Path, monkeypatch
) -> None:
    computer = AgentComputer(tmp_path)
    monkeypatch.setitem(COMMANDS, "probe", (sys.executable, "-c", "print('computer-ok')"))

    result = computer.run("probe")

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "computer-ok"
    with pytest.raises(AgentComputerError, match="Unsupported"):
        computer.run("arbitrary-shell")
