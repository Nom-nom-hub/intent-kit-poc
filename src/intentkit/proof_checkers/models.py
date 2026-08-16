"""Typed contracts for local Intent Kit proof checkers.

Checkers return observations. The core runner validates, records, aggregates, and
persists those observations as graph evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from ..kernel import IntentGraph, Node


class CheckState(StrEnum):
    """Normalized outcome of a checker execution."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class CheckerDescriptor:
    """Stable identity and capability declaration for a proof checker."""

    checker_id: str
    version: str
    display_name: str
    supported_kinds: tuple[str, ...] = ()
    needs_network: bool = False
    needs_subprocess: bool = False


@dataclass(frozen=True, slots=True)
class Artifact:
    """A project-relative artifact reference produced by a checker."""

    name: str
    path: str | None = None
    digest_sha256: str | None = None
    media_type: str | None = None


@dataclass(frozen=True, slots=True)
class CheckRequest:
    """Read-only context made available to a proof checker."""

    project_root: Path
    graph: IntentGraph
    obligation: Node
    config: Mapping[str, Any]
    run_id: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Normalized observation returned by a checker without graph mutation."""

    state: CheckState
    summary: str
    details: str = ""
    source: str = ""
    artifacts: tuple[Artifact, ...] = ()
    metrics: Mapping[str, str | int | float | bool] = field(default_factory=dict)
    external_run_id: str | None = None


class ProofChecker(Protocol):
    """Structural contract implemented by local or separately packaged checkers."""

    @property
    def descriptor(self) -> CheckerDescriptor:
        """Return the checker identity and declared capabilities."""

    def can_check(self, request: CheckRequest) -> bool:
        """Return whether this checker supports the requested obligation."""

    def run(self, request: CheckRequest) -> CheckResult:
        """Execute the check and return evidence-ready structured output."""
