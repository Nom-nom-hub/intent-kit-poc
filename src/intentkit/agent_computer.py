"""Project-scoped Agent Computer primitives with deliberate capability limits.

This module is not a general remote shell. It gives an agent a bounded local workspace,
read-only project inspection, and a small named quality-command catalog. Graph mutation
remains in the Intent Kit protocol layer, where policy and proof controls are enforced.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_READ_BYTES = 64 * 1024
MAX_WRITE_BYTES = 1024 * 1024
MAX_LISTED_FILES = 200
MAX_COMMAND_OUTPUT = 64 * 1024
MAX_COMMAND_TIMEOUT_SECONDS = 120


class AgentComputerError(ValueError):
    """Raised when an Agent Computer request exceeds its local capability boundary."""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AgentComputer:
    """A bounded computer view for one Intent Kit project directory."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.intent_root = self.project_root / ".intent"
        self.workspace_root = self.intent_root / "agent-workspace"
        self.audit_path = self.intent_root / "agent-computer-log.jsonl"

    def status(self) -> dict[str, Any]:
        workspace_files = self._workspace_files()
        return {
            "project_root": str(self.project_root),
            "workspace_root": ".intent/agent-workspace",
            "workspace_exists": self.workspace_root.is_dir(),
            "workspace_files": len(workspace_files),
            "capabilities": {
                "project_read": True,
                "workspace_write_requires_apply": True,
                "named_commands": sorted(COMMANDS),
                "arbitrary_shell": False,
                "network": False,
            },
        }

    def list_project_files(self, relative_path: str = ".") -> dict[str, Any]:
        root = self._resolve_project_path(relative_path)
        if not root.exists():
            raise AgentComputerError(f"Requested project path does not exist: {relative_path}")
        if root.is_file():
            files = [root]
        else:
            files = [
                path for path in sorted(root.rglob("*")) if path.is_file() and self._visible(path)
            ]
        limited = files[:MAX_LISTED_FILES]
        return {
            "path": (
                root.relative_to(self.project_root).as_posix() if root != self.project_root else "."
            ),
            "files": [self._file_metadata(path) for path in limited],
            "truncated": len(files) > MAX_LISTED_FILES,
            "total_visible_files": len(files),
        }

    def read_project_file(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve_project_path(relative_path)
        if not path.is_file():
            raise AgentComputerError(f"Requested project path is not a file: {relative_path}")
        size = path.stat().st_size
        if size > MAX_READ_BYTES:
            raise AgentComputerError(
                f"Requested file exceeds the {MAX_READ_BYTES} byte Agent Computer read limit."
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AgentComputerError("Agent Computer only reads UTF-8 text files.") from exc
        return {
            "path": path.relative_to(self.project_root).as_posix(),
            "content": content,
            "sha256": self._digest(path),
            "bytes": size,
        }

    def write_workspace_file(
        self, session_id: str, relative_path: str, content: str
    ) -> dict[str, Any]:
        session_root = self._session_root(session_id)
        if not isinstance(content, str):
            raise AgentComputerError("Workspace content must be a UTF-8 string.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            raise AgentComputerError(
                f"Workspace content exceeds the {MAX_WRITE_BYTES} byte Agent Computer write limit."
            )
        target = self._resolve_inside(session_root, relative_path, "workspace file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        record = {
            "action": "computer.write_file",
            "session_id": session_id,
            "path": target.relative_to(self.project_root).as_posix(),
            "sha256": self._digest(target),
            "bytes": len(encoded),
        }
        self._audit(record)
        return record

    def record(self, action: str, **details: Any) -> None:
        """Append one protocol-level action to the local Agent Computer audit log."""

        if not isinstance(action, str) or not action:
            raise AgentComputerError("Audit action must be a non-empty string.")
        self._audit({"action": action, **details})

    def run(self, command_name: str) -> dict[str, Any]:
        command = COMMANDS.get(command_name)
        if command is None:
            supported = ", ".join(sorted(COMMANDS))
            raise AgentComputerError(
                f"Unsupported Agent Computer command. Use one of: {supported}."
            )
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                env=isolated_environment(),
                text=True,
                capture_output=True,
                timeout=MAX_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
            status = "completed"
            stdout = truncate(completed.stdout)
            stderr = truncate(completed.stderr)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            status = "timed_out"
            stdout = truncate(exc.stdout or "")
            stderr = truncate(exc.stderr or "")
            exit_code = None
        record = {
            "action": "computer.run",
            "command": command_name,
            "status": status,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        }
        self._audit(record)
        return record

    def _workspace_files(self) -> list[Path]:
        if not self.workspace_root.is_dir():
            return []
        return [path for path in self.workspace_root.rglob("*") if path.is_file()]

    def _session_root(self, session_id: str) -> Path:
        if not isinstance(session_id, str) or not session_id or len(session_id) > 64:
            raise AgentComputerError("session_id must be a non-empty string up to 64 chars.")
        if not all(char.islower() or char.isdigit() or char in "-_" for char in session_id):
            raise AgentComputerError(
                "session_id may contain lowercase letters, digits, hyphens, and underscores."
            )
        root = self.workspace_root / session_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_project_path(self, relative_path: str) -> Path:
        path = self._resolve_inside(self.project_root, relative_path, "project path")
        excluded = path == self.workspace_root or self.workspace_root in path.parents
        if excluded or path == self.audit_path:
            raise AgentComputerError(
                "Project inspection excludes the agent workspace and audit log."
            )
        return path

    @staticmethod
    def _resolve_inside(root: Path, relative_path: str, label: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise AgentComputerError(f"{label} must be a non-empty relative path.")
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise AgentComputerError(f"{label} must be relative to its allowed root.")
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise AgentComputerError(f"{label} must remain inside its allowed root.") from exc
        return resolved

    def _visible(self, path: Path) -> bool:
        relative = path.relative_to(self.project_root)
        is_workspace = relative.parts[:2] == (".intent", "agent-workspace")
        is_audit_log = relative == Path(".intent/agent-computer-log.jsonl")
        return ".git" not in relative.parts and not is_workspace and not is_audit_log

    def _file_metadata(self, path: Path) -> dict[str, Any]:
        return {
            "path": path.relative_to(self.project_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": self._digest(path),
        }

    @staticmethod
    def _digest(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def _audit(self, record: dict[str, Any]) -> None:
        self.intent_root.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": utc_now(), **record}
        with self.audit_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(payload, sort_keys=True) + "\n")


def truncate(value: str) -> str:
    if len(value) <= MAX_COMMAND_OUTPUT:
        return value
    return value[:MAX_COMMAND_OUTPUT] + "\n[Agent Computer output truncated]"


def isolated_environment() -> dict[str, str]:
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    }


COMMANDS = {
    "test": (sys.executable, "-m", "pytest", "-q"),
    "lint": (sys.executable, "-m", "ruff", "check", "."),
    "format-check": (sys.executable, "-m", "ruff", "format", "--check", "."),
    "build": (sys.executable, "-m", "build"),
}
