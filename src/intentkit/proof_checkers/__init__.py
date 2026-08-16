"""Extensible, local-first proof-checker support for Intent Kit."""

from .external import ExternalCheckerRegistry, ExternalProcessChecker
from .models import Artifact, CheckerDescriptor, CheckRequest, CheckResult, CheckState, ProofChecker
from .registry import CheckerRegistry
from .runner import ProofRunner

__all__ = [
    "Artifact",
    "CheckerDescriptor",
    "CheckRequest",
    "CheckResult",
    "CheckState",
    "CheckerRegistry",
    "ExternalCheckerRegistry",
    "ExternalProcessChecker",
    "ProofChecker",
    "ProofRunner",
]
