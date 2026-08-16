"""A local, dependency-free proof checker for project file requirements."""

from __future__ import annotations

from pathlib import Path

from ..models import CheckerDescriptor, CheckRequest, CheckResult, CheckState


class FileExistsChecker:
    """Checks that a configured path exists inside the project root.

    The checker supports obligations with ``properties["checker_kind"]`` set to
    ``"file_exists"``. Configuration requires a string ``path`` and may include
    a string ``contains`` assertion for regular UTF-8 text files.
    """

    @property
    def descriptor(self) -> CheckerDescriptor:
        return CheckerDescriptor(
            checker_id="local.file-exists",
            version="1.0.0",
            display_name="Local file existence",
            supported_kinds=("file_exists",),
        )

    def can_check(self, request: CheckRequest) -> bool:
        return request.obligation.properties.get("checker_kind") == "file_exists"

    def run(self, request: CheckRequest) -> CheckResult:
        configured_path = request.config.get("path")
        if not isinstance(configured_path, str) or not configured_path.strip():
            return CheckResult(
                state=CheckState.ERROR,
                summary="File-exists checker requires a non-empty 'path' configuration value.",
                source="checker:local.file-exists",
            )

        try:
            candidate = self._resolve_inside_project(request.project_root, configured_path)
        except ValueError as exc:
            return CheckResult(
                state=CheckState.ERROR,
                summary="Configured checker path is outside the project root.",
                details=str(exc),
                source=f"path:{configured_path}",
            )

        source = candidate.relative_to(request.project_root).as_posix()
        if not candidate.exists():
            return CheckResult(
                state=CheckState.FAIL,
                summary=f"Required path does not exist: {source}.",
                source=source,
                metrics={"exists": False},
            )

        expected_text = request.config.get("contains")
        if expected_text is not None:
            if not isinstance(expected_text, str):
                return CheckResult(
                    state=CheckState.ERROR,
                    summary="'contains' must be a string when provided.",
                    source=source,
                )
            if not candidate.is_file():
                return CheckResult(
                    state=CheckState.ERROR,
                    summary="A text-content assertion requires a regular file.",
                    source=source,
                )
            try:
                content = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return CheckResult(
                    state=CheckState.ERROR,
                    summary="A text-content assertion requires a UTF-8 text file.",
                    source=source,
                )
            if expected_text not in content:
                return CheckResult(
                    state=CheckState.FAIL,
                    summary=f"Required text was not found in {source}.",
                    source=source,
                    metrics={"exists": True, "contains": False},
                )

        return CheckResult(
            state=CheckState.PASS,
            summary=f"Required path is present: {source}.",
            source=source,
            metrics={"exists": True, "contains": expected_text is None or True},
        )

    @staticmethod
    def _resolve_inside_project(project_root: Path, configured_path: str) -> Path:
        root = project_root.resolve()
        candidate = (root / configured_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"{configured_path!r} resolves outside {root}")
        return candidate
