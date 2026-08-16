#!/usr/bin/env python3
"""Reference external checker for Intent Kit's pinned JSON subprocess protocol."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def result(state: str, summary: str, source: str, **extra: Any) -> None:
    payload = {"state": state, "summary": summary, "source": source, **extra}
    print(json.dumps(payload, sort_keys=True))


def project_path(raw_path: str) -> Path:
    root = Path.cwd().resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Configured path must remain inside the project root.") from exc
    return candidate


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        result("error", "Request was not valid JSON.", "external:example.file-content")
        return 0
    if request.get("protocol_version") != 1:
        result(
            "error",
            "Unsupported Intent Kit checker protocol version.",
            "external:example.file-content",
        )
        return 0
    config = request.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("path"), str):
        result(
            "error",
            "Checker configuration requires a string path.",
            "external:example.file-content",
        )
        return 0
    try:
        candidate = project_path(config["path"])
    except ValueError as exc:
        result("error", str(exc), "external:example.file-content")
        return 0
    source = candidate.relative_to(Path.cwd().resolve()).as_posix()
    if not candidate.is_file():
        result("fail", f"Required file is missing: {source}.", source, metrics={"exists": False})
        return 0
    expected = config.get("contains")
    if expected is not None:
        if not isinstance(expected, str):
            result("error", "Optional contains configuration must be a string.", source)
            return 0
        content = candidate.read_text(encoding="utf-8")
        if expected not in content:
            result(
                "fail",
                f"Required text was not found in {source}.",
                source,
                metrics={"exists": True, "contains": False},
            )
            return 0
    digest = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
    result(
        "pass",
        f"Required file and configured content are present: {source}.",
        source,
        artifacts=[
            {
                "name": source,
                "path": source,
                "digest_sha256": digest,
                "media_type": "text/markdown" if candidate.suffix == ".md" else None,
            }
        ],
        metrics={"exists": True, "contains": expected is None or True},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
