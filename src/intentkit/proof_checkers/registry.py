"""Explicit local registry for Intent Kit proof checkers."""

from __future__ import annotations

from .models import CheckerDescriptor, ProofChecker


class CheckerRegistry:
    """Registers trusted in-process checkers by a stable checker identifier.

    Entry-point discovery and external package allowlisting are intentionally not
    enabled in this first implementation. Callers must register each checker
    explicitly, making loaded code visible in the application configuration.
    """

    def __init__(self) -> None:
        self._checkers: dict[str, ProofChecker] = {}

    def register(self, checker: ProofChecker) -> None:
        descriptor = checker.descriptor
        self._validate_descriptor(descriptor)
        if descriptor.checker_id in self._checkers:
            raise ValueError(f"A checker is already registered for {descriptor.checker_id!r}.")
        self._checkers[descriptor.checker_id] = checker

    def resolve(self, checker_id: str) -> ProofChecker:
        try:
            return self._checkers[checker_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._checkers)) or "none"
            raise ValueError(f"Unknown checker {checker_id!r}. Registered checkers: {available}.") from exc

    def descriptors(self) -> tuple[CheckerDescriptor, ...]:
        return tuple(
            self._checkers[checker_id].descriptor
            for checker_id in sorted(self._checkers)
        )

    @staticmethod
    def _validate_descriptor(descriptor: CheckerDescriptor) -> None:
        if not descriptor.checker_id or "." not in descriptor.checker_id:
            raise ValueError("Checker IDs must be non-empty dotted identifiers, e.g. 'local.file-exists'.")
        if not descriptor.version:
            raise ValueError(f"Checker {descriptor.checker_id!r} must declare a version.")
        if not descriptor.display_name:
            raise ValueError(f"Checker {descriptor.checker_id!r} must declare a display name.")
