"""Core orchestration for running checkers and recording graph evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..kernel import GraphStore, IntentGraph, NodeStatus, NodeType, RelationType, utc_now
from ..renderer import MarkdownRenderer
from .models import Artifact, CheckerDescriptor, CheckRequest, CheckResult, CheckState
from .registry import CheckerRegistry

MAX_DETAIL_CHARS = 8_000
SUPPORTED_EVALUATIONS = {"latest", "all", "any", "manual"}


class ProofRunner:
    """Runs registered checkers without granting them graph persistence control."""

    def __init__(self, store: GraphStore, registry: CheckerRegistry):
        self.store = store
        self.registry = registry

    def run(
        self, obligation_id: str, checker_id: str, config: Mapping[str, Any] | None = None
    ) -> CheckResult:
        graph = self.store.load()
        obligation = graph.get_node(obligation_id)
        if obligation.type != NodeType.PROOF_OBLIGATION.value:
            raise ValueError(f"{obligation_id} is a {obligation.type}, not a proof obligation.")
        checker = self.registry.resolve(checker_id)
        normalized_config = dict(config or {})
        timeout_seconds = self._read_timeout(normalized_config)
        run_id = f"run-{uuid4().hex[:16]}"
        request = CheckRequest(
            project_root=self.store.project_root,
            graph=graph,
            obligation=obligation,
            config=normalized_config,
            run_id=run_id,
            timeout_seconds=timeout_seconds,
        )

        started = perf_counter()
        try:
            result = self._execute_checker(checker, request)
        except Exception as exc:  # Defensive boundary around third-party checker code.
            result = CheckResult(
                state=CheckState.ERROR,
                summary="Checker execution raised an unexpected error.",
                details=type(exc).__name__,
                source=f"checker:{checker.descriptor.checker_id}",
            )
        duration_ms = int((perf_counter() - started) * 1000)
        result = self._normalize_result(result, checker.descriptor, duration_ms)

        evidence = graph.add_node(
            NodeType.EVIDENCE,
            title=f"{checker.descriptor.display_name}: {result.summary}",
            description=result.details or result.summary,
            status=evidence_status(result.state),
            properties=serialize_result(
                result, checker.descriptor, run_id, normalized_config, duration_ms
            ),
        )
        graph.add_edge(evidence.id, obligation.id, RelationType.PROVES)
        graph.set_status(obligation.id, aggregate_obligation_status(graph, obligation.id))
        self.store.save(graph)
        MarkdownRenderer(self.store.project_root).render(graph)
        return result

    @staticmethod
    def _read_timeout(config: Mapping[str, Any]) -> int:
        value = config.get("timeout_seconds", 60)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3_600:
            raise ValueError("timeout_seconds must be an integer from 1 through 3600.")
        return value

    @staticmethod
    def _execute_checker(checker, request: CheckRequest) -> CheckResult:
        if not checker.can_check(request):
            return CheckResult(
                state=CheckState.SKIPPED,
                summary="Checker does not support this proof obligation.",
                source=f"checker:{checker.descriptor.checker_id}",
            )
        result = checker.run(request)
        if not isinstance(result, CheckResult):
            raise TypeError("Proof checkers must return CheckResult instances.")
        return result

    @staticmethod
    def _normalize_result(
        result: CheckResult, descriptor: CheckerDescriptor, duration_ms: int
    ) -> CheckResult:
        summary = result.summary.strip()
        if not summary:
            return CheckResult(
                state=CheckState.ERROR,
                summary="Checker returned an empty summary.",
                source=f"checker:{descriptor.checker_id}",
            )
        metrics = dict(result.metrics)
        metrics["duration_ms"] = duration_ms
        return replace(
            result,
            summary=summary[:500],
            details=result.details.strip()[:MAX_DETAIL_CHARS],
            source=(result.source.strip() or f"checker:{descriptor.checker_id}")[:1000],
            metrics=metrics,
        )


def evidence_status(state: CheckState) -> NodeStatus:
    if state is CheckState.PASS:
        return NodeStatus.VERIFIED
    if state is CheckState.FAIL:
        return NodeStatus.FAILED
    return NodeStatus.ACTIVE


def aggregate_obligation_status(graph: IntentGraph, obligation_id: str) -> NodeStatus:
    """Compute a compatible node status from immutable historical evidence."""

    obligation = graph.get_node(obligation_id)
    if obligation.type != NodeType.PROOF_OBLIGATION.value:
        raise ValueError(f"{obligation_id} is not a proof obligation.")
    evaluation = obligation.properties.get("evaluation", "latest")
    if evaluation not in SUPPORTED_EVALUATIONS:
        supported = ", ".join(sorted(SUPPORTED_EVALUATIONS))
        raise ValueError(
            f"Unsupported proof evaluation {evaluation!r}; expected one of {supported}."
        )
    if evaluation == "manual":
        return NodeStatus(obligation.status)

    evidence = evidence_for_obligation(graph, obligation_id)
    if not evidence:
        return NodeStatus.ACTIVE
    if evaluation == "latest":
        return state_to_node_status(evidence[-1].properties.get("result"))
    if evaluation == "all":
        return all_policy_status(obligation.properties, evidence)
    return any_policy_status(obligation.properties, evidence)


def evidence_for_obligation(graph: IntentGraph, obligation_id: str):
    edges = graph.incoming(obligation_id, RelationType.PROVES)
    nodes = [graph.get_node(edge.source) for edge in edges]
    return sorted(nodes, key=lambda node: (node.created_at, node.id))


def all_policy_status(properties: Mapping[str, Any], evidence) -> NodeStatus:
    latest_by_checker = latest_evidence_by_checker(evidence)
    required = required_checker_ids(properties)
    if required:
        required_evidence = [latest_by_checker.get(checker_id) for checker_id in required]
        if any(item is None for item in required_evidence):
            return NodeStatus.ACTIVE
        results = [item.properties.get("result") for item in required_evidence if item is not None]
    else:
        results = [node.properties.get("result") for node in evidence]
    if any(result == CheckState.FAIL.value for result in results):
        return NodeStatus.FAILED
    if results and all(result == CheckState.PASS.value for result in results):
        return NodeStatus.VERIFIED
    return NodeStatus.ACTIVE


def any_policy_status(properties: Mapping[str, Any], evidence) -> NodeStatus:
    results = [node.properties.get("result") for node in evidence]
    if CheckState.PASS.value in results:
        return NodeStatus.VERIFIED
    required = required_checker_ids(properties)
    if required:
        latest_by_checker = latest_evidence_by_checker(evidence)
        required_evidence = [latest_by_checker.get(checker_id) for checker_id in required]
        if any(item is None for item in required_evidence):
            return NodeStatus.ACTIVE
        results = [item.properties.get("result") for item in required_evidence if item is not None]
    if results and all(result == CheckState.FAIL.value for result in results):
        return NodeStatus.FAILED
    return NodeStatus.ACTIVE


def state_to_node_status(result: Any) -> NodeStatus:
    if result == CheckState.PASS.value:
        return NodeStatus.VERIFIED
    if result == CheckState.FAIL.value:
        return NodeStatus.FAILED
    return NodeStatus.ACTIVE


def required_checker_ids(properties: Mapping[str, Any]) -> tuple[str, ...]:
    configured = properties.get("required_checkers", [])
    if configured is None:
        return ()
    if not isinstance(configured, list) or not all(
        isinstance(item, str) and item for item in configured
    ):
        raise ValueError("required_checkers must be a list of non-empty checker IDs.")
    return tuple(configured)


def latest_evidence_by_checker(evidence) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for node in evidence:
        checker = node.properties.get("checker", {})
        checker_id = checker.get("id") if isinstance(checker, dict) else None
        if isinstance(checker_id, str) and checker_id:
            latest[checker_id] = node
    return latest


def serialize_result(
    result: CheckResult,
    descriptor: CheckerDescriptor,
    run_id: str,
    config: Mapping[str, Any],
    duration_ms: int,
) -> dict[str, Any]:
    return {
        "result": result.state.value,
        "source": result.source,
        "summary": result.summary,
        "details": result.details,
        "checker": {"id": descriptor.checker_id, "version": descriptor.version},
        "run": {
            "id": run_id,
            "executed_at": utc_now(),
            "duration_ms": duration_ms,
            "config_fingerprint": configuration_fingerprint(config),
        },
        "artifacts": [artifact_to_dict(artifact) for artifact in result.artifacts],
        "metrics": dict(result.metrics),
        "external_run_id": result.external_run_id,
    }


def configuration_fingerprint(config: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            config, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Checker configuration must be JSON-serializable.") from exc
    return "sha256:" + sha256(encoded).hexdigest()


def artifact_to_dict(artifact: Artifact) -> dict[str, Any]:
    return {
        "name": artifact.name,
        "path": artifact.path,
        "digest_sha256": artifact.digest_sha256,
        "media_type": artifact.media_type,
    }
