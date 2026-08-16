"""Controlled, project-local external proof checker execution.

External checkers are never discovered from the Python environment. A project must
explicitly allow each checker in `.intent/external-checkers.json`, pin the manifest
and entrypoint digests, and run a JSON-only subprocess protocol. This is process
isolation and provenance control, not a replacement for an operating-system sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Artifact, CheckerDescriptor, CheckRequest, CheckResult, CheckState

ALLOWLIST_SCHEMA_VERSION = "1"
MANIFEST_PROTOCOL_VERSION = 1
ALLOWLIST_FILENAME = "external-checkers.json"
MANIFEST_FILENAME = "intentkit-checker.json"
MAX_STDOUT_CHARS = 32_000
MAX_STDERR_CHARS = 4_000
CHECKER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")


@dataclass(frozen=True, slots=True)
class ExternalCheckerManifest:
    """Validated immutable description of one external checker process."""

    checker_id: str
    version: str
    display_name: str
    supported_kinds: tuple[str, ...]
    manifest_path: Path
    entrypoint: Path
    entrypoint_sha256: str
    max_timeout_seconds: int

    @property
    def descriptor(self) -> CheckerDescriptor:
        return CheckerDescriptor(
            checker_id=self.checker_id,
            version=self.version,
            display_name=self.display_name,
            supported_kinds=self.supported_kinds,
            needs_subprocess=True,
        )


class ExternalProcessChecker:
    """A pinned external checker that only exchanges JSON with the core process."""

    def __init__(self, manifest: ExternalCheckerManifest):
        self.manifest = manifest

    @property
    def descriptor(self) -> CheckerDescriptor:
        return self.manifest.descriptor

    def can_check(self, request: CheckRequest) -> bool:
        kind = request.obligation.properties.get("checker_kind")
        return isinstance(kind, str) and kind in self.manifest.supported_kinds

    def run(self, request: CheckRequest) -> CheckResult:
        try:
            ensure_digest(
                self.manifest.entrypoint,
                self.manifest.entrypoint_sha256,
                "entrypoint before execution",
            )
        except ValueError as exc:
            return CheckResult(
                state=CheckState.ERROR,
                summary="External checker entrypoint changed after authorization.",
                details=str(exc),
                source=f"external:{self.manifest.checker_id}",
            )
        timeout_seconds = min(request.timeout_seconds, self.manifest.max_timeout_seconds)
        payload = {
            "protocol_version": MANIFEST_PROTOCOL_VERSION,
            "run_id": request.run_id,
            "obligation": {
                "id": request.obligation.id,
                "title": request.obligation.title,
                "description": request.obligation.description,
                "properties": request.obligation.properties,
            },
            "config": dict(request.config),
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(self.manifest.entrypoint)],
                input=json.dumps(payload, sort_keys=True),
                text=True,
                capture_output=True,
                cwd=request.project_root,
                env=isolated_environment(),
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return CheckResult(
                state=CheckState.ERROR,
                summary=f"External checker timed out after {timeout_seconds} second(s).",
                source=f"external:{self.manifest.checker_id}",
            )
        except OSError as exc:
            return CheckResult(
                state=CheckState.ERROR,
                summary="External checker process could not be started.",
                details=type(exc).__name__,
                source=f"external:{self.manifest.checker_id}",
            )
        if completed.returncode != 0:
            return CheckResult(
                state=CheckState.ERROR,
                summary=f"External checker exited with code {completed.returncode}.",
                details=completed.stderr[:MAX_STDERR_CHARS],
                source=f"external:{self.manifest.checker_id}",
            )
        if len(completed.stdout) > MAX_STDOUT_CHARS:
            return CheckResult(
                state=CheckState.ERROR,
                summary="External checker output exceeded the allowed size.",
                source=f"external:{self.manifest.checker_id}",
            )
        return parse_external_result(completed.stdout, self.manifest)


class ExternalCheckerRegistry:
    """Loads explicitly allowed external checkers from a project-local JSON file."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.config_path = self.project_root / ".intent" / ALLOWLIST_FILENAME

    def load(self) -> tuple[ExternalProcessChecker, ...]:
        if not self.config_path.exists():
            return ()
        payload = read_json_object(self.config_path, "External checker allowlist")
        if payload.get("schema_version") != ALLOWLIST_SCHEMA_VERSION:
            raise ValueError(
                f"External checker allowlist schema_version must be '{ALLOWLIST_SCHEMA_VERSION}'."
            )
        configured = payload.get("checkers")
        if not isinstance(configured, list):
            raise ValueError("External checker allowlist requires a 'checkers' list.")
        checkers: list[ExternalProcessChecker] = []
        seen: set[str] = set()
        for entry in configured:
            manifest = self._load_entry(entry)
            if manifest.checker_id in seen:
                raise ValueError(
                    f"External checker allowlist contains duplicate ID '{manifest.checker_id}'."
                )
            seen.add(manifest.checker_id)
            checkers.append(ExternalProcessChecker(manifest))
        return tuple(sorted(checkers, key=lambda checker: checker.descriptor.checker_id))

    def write_template(self) -> Path:
        if self.config_path.exists():
            raise FileExistsError(f"External checker allowlist already exists: {self.config_path}")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "schema_version": ALLOWLIST_SCHEMA_VERSION,
                    "checkers": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return self.config_path

    def _load_entry(self, entry: Any) -> ExternalCheckerManifest:
        if not isinstance(entry, dict):
            raise ValueError("Each external checker allowlist entry must be a JSON object.")
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError("External checker 'enabled' must be a boolean.")
        if not enabled:
            raise ValueError("Disabled external checkers must be removed from the allowlist.")
        checker_id = required_string(entry, "checker_id", "External checker allowlist")
        version = required_string(entry, "version", "External checker allowlist")
        validate_identity(checker_id, version)
        manifest_ref = required_string(entry, "manifest", "External checker allowlist")
        manifest_path = resolve_inside(self.project_root, manifest_ref, "manifest")
        expected_manifest_digest = required_digest(entry, "manifest_sha256")
        ensure_digest(manifest_path, expected_manifest_digest, "manifest")
        manifest_payload = read_json_object(manifest_path, "External checker manifest")
        manifest = manifest_from_payload(manifest_payload, manifest_path, self.project_root)
        if manifest.checker_id != checker_id or manifest.version != version:
            raise ValueError(
                "External checker allowlist identity must exactly match the pinned "
                "manifest identity."
            )
        return manifest


def manifest_from_payload(
    payload: dict[str, Any], manifest_path: Path, project_root: Path
) -> ExternalCheckerManifest:
    """Validate a pinned checker manifest without executing any extension code."""

    if payload.get("protocol_version") != MANIFEST_PROTOCOL_VERSION:
        raise ValueError(
            f"External checker manifest protocol_version must be {MANIFEST_PROTOCOL_VERSION}."
        )
    checker_id = required_string(payload, "checker_id", "External checker manifest")
    version = required_string(payload, "version", "External checker manifest")
    validate_identity(checker_id, version)
    display_name = required_string(payload, "display_name", "External checker manifest")
    supported_kinds = payload.get("supported_kinds")
    if (
        not isinstance(supported_kinds, list)
        or not supported_kinds
        or not all(isinstance(kind, str) and kind.strip() for kind in supported_kinds)
    ):
        raise ValueError(
            "External checker manifest supported_kinds must be a non-empty string list."
        )
    if payload.get("needs_network", False) is not False:
        raise ValueError(
            "External checkers declaring network access are not supported in this release."
        )
    entrypoint_ref = required_string(payload, "entrypoint", "External checker manifest")
    entrypoint = resolve_inside(
        project_root, str(manifest_path.parent / entrypoint_ref), "entrypoint"
    )
    entrypoint_digest = required_digest(payload, "entrypoint_sha256")
    ensure_digest(entrypoint, entrypoint_digest, "entrypoint")
    max_timeout = payload.get("max_timeout_seconds", 60)
    invalid_timeout = (
        isinstance(max_timeout, bool)
        or not isinstance(max_timeout, int)
        or not 1 <= max_timeout <= 300
    )
    if invalid_timeout:
        raise ValueError(
            "External checker manifest max_timeout_seconds must be an integer from 1 through 300."
        )
    return ExternalCheckerManifest(
        checker_id=checker_id,
        version=version,
        display_name=display_name,
        supported_kinds=tuple(supported_kinds),
        manifest_path=manifest_path,
        entrypoint=entrypoint,
        entrypoint_sha256=entrypoint_digest,
        max_timeout_seconds=max_timeout,
    )


def parse_external_result(raw_output: str, manifest: ExternalCheckerManifest) -> CheckResult:
    """Convert the subprocess JSON result into the existing typed result contract."""

    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return protocol_error(manifest, f"External checker returned invalid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return protocol_error(manifest, "External checker result must be a JSON object.")
    state_raw = payload.get("state")
    try:
        state = CheckState(state_raw)
    except (TypeError, ValueError):
        return protocol_error(manifest, "External checker result has an unsupported state.")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return protocol_error(manifest, "External checker result requires a non-empty summary.")
    details = payload.get("details", "")
    source = payload.get("source", f"external:{manifest.checker_id}")
    metrics = payload.get("metrics", {})
    external_run_id = payload.get("external_run_id")
    if not isinstance(details, str) or not isinstance(source, str):
        return protocol_error(manifest, "External checker details and source must be strings.")
    if not isinstance(metrics, dict) or not all(
        isinstance(value, (str, int, float, bool)) and not isinstance(value, type(None))
        for value in metrics.values()
    ):
        return protocol_error(manifest, "External checker metrics must be scalar JSON values.")
    if external_run_id is not None and not isinstance(external_run_id, str):
        return protocol_error(
            manifest, "External checker external_run_id must be a string or null."
        )
    artifacts = parse_artifacts(payload.get("artifacts", []), manifest)
    if artifacts is None:
        return protocol_error(manifest, "External checker artifacts must be JSON object records.")
    return CheckResult(
        state=state,
        summary=summary,
        details=details,
        source=source,
        artifacts=artifacts,
        metrics=metrics,
        external_run_id=external_run_id,
    )


def parse_artifacts(
    raw_artifacts: Any, manifest: ExternalCheckerManifest
) -> tuple[Artifact, ...] | None:
    if not isinstance(raw_artifacts, list):
        return None
    artifacts: list[Artifact] = []
    for item in raw_artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            return None
        name = item["name"].strip()
        path = item.get("path")
        digest = item.get("digest_sha256")
        media_type = item.get("media_type")
        if not name or path is not None and not isinstance(path, str):
            return None
        if isinstance(path, str):
            path_ref = Path(path)
            if path_ref.is_absolute() or ".." in path_ref.parts:
                return None
        if digest is not None and (not isinstance(digest, str) or not digest.startswith("sha256:")):
            return None
        if media_type is not None and not isinstance(media_type, str):
            return None
        artifacts.append(
            Artifact(name=name, path=path, digest_sha256=digest, media_type=media_type)
        )
    return tuple(artifacts)


def protocol_error(manifest: ExternalCheckerManifest, summary: str) -> CheckResult:
    return CheckResult(
        state=CheckState.ERROR,
        summary=summary,
        source=f"external:{manifest.checker_id}",
    )


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return payload


def required_string(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} requires a non-empty '{key}' string.")
    return value.strip()


def required_digest(payload: dict[str, Any], key: str) -> str:
    value = required_string(payload, key, "External checker configuration")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError(f"External checker '{key}' must be a sha256: hexadecimal digest.")
    return value


def validate_identity(checker_id: str, version: str) -> None:
    if not CHECKER_ID_PATTERN.fullmatch(checker_id):
        raise ValueError("External checker IDs must be lowercase dotted identifiers.")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("External checker versions must use a semantic-version-like value.")


def resolve_inside(project_root: Path, path_ref: str, label: str) -> Path:
    root = project_root.resolve()
    candidate = Path(path_ref)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"External checker {label} must resolve inside the project root.") from exc
    if not resolved.is_file():
        raise ValueError(f"External checker {label} does not exist: {resolved}")
    return resolved


def ensure_digest(path: Path, expected: str, label: str) -> None:
    current = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if current != expected:
        raise ValueError(
            f"External checker {label} digest mismatch for {path}. "
            f"Expected {expected}, got {current}."
        )


def isolated_environment() -> dict[str, str]:
    """Provide a minimal environment and suppress ambient Python import configuration."""

    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    }
