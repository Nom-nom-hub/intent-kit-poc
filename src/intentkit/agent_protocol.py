"""Machine-readable, policy-preserving access to Intent Kit projects.

The agent protocol intentionally exposes a small JSON command surface rather than a
free-form shell. Every operation uses the same graph store, policy registry, checker
registry, and proof runner as the human CLI. Mutating operations use an explicit
``--apply`` gate and are routed through typed graph and workspace handlers.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .agent_computer import AgentComputer, AgentComputerError
from .importers import SpecKitSynchronizer, SyncProposal
from .insights import DriftRecord, ImpactPath, ImpactReport, analyze_impact, scan_drift
from .kernel import GraphStore, IntentGraph, Node, NodeStatus, NodeType, RelationType
from .policies import PolicyRegistry
from .proof_checkers.models import CheckerDescriptor
from .proof_checkers.registry import CheckerRegistry
from .proof_checkers.runner import ProofRunner, aggregate_obligation_status
from .renderer import MarkdownRenderer

PROTOCOL_VERSION = 1
READ_OPERATIONS = frozenset(
    {"snapshot", "status", "drift", "impact", "policies", "checkers", "sync.propose"}
)
COMPUTER_READ_OPERATIONS = frozenset(
    {"computer.status", "computer.list_files", "computer.read_file"}
)
COMPUTER_RUN_OPERATIONS = frozenset({"computer.run"})
MUTATION_OPERATIONS = frozenset(
    {"capture", "shape", "prove", "check", "sync.apply", "computer.write_file"}
)
ALL_OPERATIONS = (
    READ_OPERATIONS | COMPUTER_READ_OPERATIONS | COMPUTER_RUN_OPERATIONS | MUTATION_OPERATIONS
)


class AgentProtocolError(ValueError):
    """Structured request-validation error with a stable machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_request(raw: str) -> dict[str, Any]:
    """Validate a JSON protocol request before touching a project."""

    import json

    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentProtocolError("invalid_json", f"Request is not valid JSON: {exc.msg}.") from exc
    if not isinstance(request, dict):
        raise AgentProtocolError("invalid_request", "Agent request must be a JSON object.")
    expected_version = request.get("protocol_version")
    if expected_version != PROTOCOL_VERSION:
        raise AgentProtocolError(
            "unsupported_protocol",
            f"protocol_version must be {PROTOCOL_VERSION}.",
        )
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise AgentProtocolError(
            "invalid_request",
            "request_id must be a non-empty string up to 128 chars.",
        )
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in ALL_OPERATIONS:
        supported = ", ".join(sorted(ALL_OPERATIONS))
        raise AgentProtocolError("unsupported_operation", f"operation must be one of: {supported}.")
    arguments = request.get("arguments", {})
    if not isinstance(arguments, dict):
        raise AgentProtocolError("invalid_arguments", "arguments must be a JSON object.")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id.strip(),
        "operation": operation,
        "arguments": arguments,
    }


def execute_read(
    project_root: Path,
    request: Mapping[str, Any],
    checker_descriptors: tuple[CheckerDescriptor, ...],
) -> dict[str, Any]:
    """Execute one read-only request and return an envelope ready for JSON output."""

    operation = request["operation"]
    if operation not in READ_OPERATIONS:
        raise AgentProtocolError(
            "apply_required",
            f"Operation '{operation}' mutates the graph and requires --apply.",
        )
    store = GraphStore(project_root)
    graph = store.load()
    arguments = request["arguments"]
    if operation == "snapshot":
        include_graph = optional_bool(arguments, "include_graph", default=False)
        result: dict[str, Any] = {"summary": graph_summary(graph)}
        if include_graph:
            result["graph"] = graph.to_dict()
    elif operation == "status":
        result = graph_summary(graph)
    elif operation == "drift":
        source = optional_project_path(project_root, arguments, "source")
        result = {"records": [drift_to_dict(record) for record in scan_drift(graph, source)]}
    elif operation == "impact":
        node_id = required_string(arguments, "node_id")
        result = impact_to_dict(analyze_impact(graph, node_id))
    elif operation == "policies":
        registry = PolicyRegistry.from_project(project_root)
        result = {"packs": [pack.to_properties() for pack in registry.list()]}
    elif operation == "sync.propose":
        source = required_project_directory(project_root, arguments, "source")
        proposal = SpecKitSynchronizer(source).propose(graph)
        result = {"proposal": proposal.to_dict()}
    else:
        result = {
            "checkers": [descriptor_to_dict(descriptor) for descriptor in checker_descriptors],
        }
    return response(request, result=result, applied=False)


def graph_summary(graph: IntentGraph) -> dict[str, Any]:
    """Return stable high-level state without forcing agents to parse Markdown."""

    counts = {node_type.value: 0 for node_type in NodeType}
    policy_counts: dict[str, int] = {}
    obligations: list[Node] = []
    for node in graph.nodes.values():
        counts[node.type] += 1
        if node.type == NodeType.PROOF_OBLIGATION.value:
            obligations.append(node)
        if node.type == NodeType.REQUIREMENT.value:
            policy = node.properties.get("policy_pack")
            if isinstance(policy, dict) and isinstance(policy.get("name"), str):
                name = policy["name"]
                policy_counts[name] = policy_counts.get(name, 0) + 1
    verified = sum(node.status == NodeStatus.VERIFIED.value for node in obligations)
    failed = sum(node.status == NodeStatus.FAILED.value for node in obligations)
    return {
        "project_name": graph.project_name,
        "graph_schema_version": graph.schema_version,
        "graph_updated_at": graph.updated_at,
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "node_counts": {key: value for key, value in counts.items() if value},
        "proof_coverage": {
            "total": len(obligations),
            "verified": verified,
            "failed": failed,
            "gaps": len(obligations) - verified - failed,
        },
        "policy_counts": dict(sorted(policy_counts.items())),
    }


def response(
    request: Mapping[str, Any], *, result: Mapping[str, Any], applied: bool
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request["request_id"],
        "operation": request["operation"],
        "ok": True,
        "applied": applied,
        "result": dict(result),
    }


def error_response(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": False,
        "error": {"code": code, "message": message},
    }


def descriptor_to_dict(descriptor: CheckerDescriptor) -> dict[str, Any]:
    return {
        "checker_id": descriptor.checker_id,
        "version": descriptor.version,
        "display_name": descriptor.display_name,
        "supported_kinds": list(descriptor.supported_kinds),
        "needs_network": descriptor.needs_network,
        "needs_subprocess": descriptor.needs_subprocess,
    }


def drift_to_dict(record: DriftRecord) -> dict[str, Any]:
    return {
        "source_root": record.source_root,
        "artifact": record.artifact,
        "expected_digest": record.expected_digest,
        "current_digest": record.current_digest,
        "status": record.status.value,
        "node_ids": list(record.node_ids),
    }


def impact_to_dict(report: ImpactReport) -> dict[str, Any]:
    return {
        "root": node_to_dict(report.root),
        "paths": [impact_path_to_dict(path) for path in report.paths],
        "proof_gaps": [node_to_dict(node) for node in report.proof_gaps],
    }


def impact_path_to_dict(path: ImpactPath) -> dict[str, Any]:
    return {
        "node": node_to_dict(path.node),
        "hops": [
            {
                "edge_id": hop.edge_id,
                "relation": hop.relation,
                "direction": hop.direction,
                "node_id": hop.node_id,
            }
            for hop in path.hops
        ],
    }


def node_to_dict(node: Node) -> dict[str, Any]:
    return {
        "id": node.id,
        "type": node.type,
        "title": node.title,
        "description": node.description,
        "status": node.status,
        "properties": node.properties,
    }


def required_string(arguments: Mapping[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentProtocolError(
            "invalid_arguments", f"arguments.{key} must be a non-empty string."
        )
    return value.strip()


def optional_bool(arguments: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = arguments.get(key, default)
    if not isinstance(value, bool):
        raise AgentProtocolError("invalid_arguments", f"arguments.{key} must be a boolean.")
    return value


def optional_project_path(
    project_root: Path, arguments: Mapping[str, Any], key: str
) -> Path | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentProtocolError("invalid_arguments", f"arguments.{key} must be a path string.")
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()


def execute_computer(
    project_root: Path, request: Mapping[str, Any], *, apply: bool
) -> dict[str, Any]:
    """Execute one bounded Agent Computer operation through the JSON protocol."""

    computer = AgentComputer(project_root)
    operation = request["operation"]
    arguments = request["arguments"]
    try:
        if operation == "computer.status":
            result = computer.status()
            applied = False
        elif operation == "computer.list_files":
            relative_path = optional_string(arguments, "path", default=".")
            result = computer.list_project_files(relative_path)
            applied = False
        elif operation == "computer.read_file":
            result = computer.read_project_file(required_string(arguments, "path"))
            applied = False
        elif operation == "computer.run":
            result = computer.run(required_string(arguments, "command"))
            applied = False
        elif operation == "computer.write_file":
            if not apply:
                return mutation_preview(request)
            result = computer.write_workspace_file(
                required_string(arguments, "session_id"),
                required_string(arguments, "path"),
                required_content(arguments, "content"),
            )
            applied = True
        else:
            raise AgentProtocolError(
                "unsupported_operation", f"Unsupported Agent Computer operation: {operation}"
            )
    except AgentComputerError as exc:
        raise AgentProtocolError("computer_error", str(exc)) from exc
    return response(request, result=result, applied=applied)


def mutation_preview(request: Mapping[str, Any]) -> dict[str, Any]:
    """Return a non-mutating proposal envelope when explicit apply is absent."""

    return response(
        request,
        result={
            "requires_apply": True,
            "operation": request["operation"],
            "arguments": request["arguments"],
            "message": (
                "No project state changed. Resubmit this exact request with --apply after approval."
            ),
        },
        applied=False,
    )


def execute_mutation(
    project_root: Path,
    request: Mapping[str, Any],
    checker_registry: CheckerRegistry,
    *,
    apply: bool,
) -> dict[str, Any]:
    """Apply typed graph mutations only when the protocol caller sets ``--apply``."""

    if not apply:
        return mutation_preview(request)
    operation = request["operation"]
    arguments = request["arguments"]
    if operation == "computer.write_file":
        return execute_computer(project_root, request, apply=True)
    store = GraphStore(project_root)
    if operation == "sync.apply":
        result = apply_sync(store, project_root, arguments)
        AgentComputer(project_root).record(
            "agent.apply",
            request_id=request["request_id"],
            operation=operation,
            result_keys=sorted(result),
        )
        return response(request, result=result, applied=True)
    graph = store.load()
    computer = AgentComputer(project_root)
    if operation == "capture":
        outcome = graph.add_node(
            NodeType.OUTCOME,
            required_string(arguments, "title"),
            required_string(arguments, "description"),
            status=NodeStatus.ACTIVE,
            properties={
                "success_measures": string_list(arguments, "success_measures"),
                "assumptions": string_list(arguments, "assumptions"),
            },
        )
        store.save(graph)
        MarkdownRenderer(project_root).render(graph)
        result: dict[str, Any] = {"created": [node_to_dict(outcome)]}
    elif operation == "shape":
        result = apply_shape(graph, project_root, arguments)
        store.save(graph)
        MarkdownRenderer(project_root).render(graph)
    elif operation == "prove":
        result = apply_prove(graph, arguments)
        store.save(graph)
        MarkdownRenderer(project_root).render(graph)
    elif operation == "check":
        check_result = ProofRunner(store, checker_registry).run(
            required_string(arguments, "obligation_id"),
            required_string(arguments, "checker_id"),
            required_object(arguments, "config", default={}),
        )
        result = {
            "check": {
                "state": check_result.state.value,
                "summary": check_result.summary,
                "details": check_result.details,
                "source": check_result.source,
                "metrics": check_result.metrics,
            }
        }
    else:
        raise AgentProtocolError(
            "unsupported_operation", f"Unsupported mutation operation: {operation}"
        )
    computer.record(
        "agent.apply",
        request_id=request["request_id"],
        operation=operation,
        result_keys=sorted(result),
    )
    return response(request, result=result, applied=True)


def apply_sync(
    store: GraphStore, project_root: Path, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    source = required_project_directory(project_root, arguments, "source")
    proposal = SyncProposal.from_dict(required_object(arguments, "proposal", default={}))
    synchronizer = SpecKitSynchronizer(source)
    if proposal.source_root != str(synchronizer.source_root):
        raise AgentProtocolError(
            "invalid_arguments", "proposal source_root does not match arguments.source."
        )
    synchronizer.write_proposal(store, proposal)
    report = synchronizer.apply(store, proposal)
    return {
        "sync": {
            "proposal_id": report.proposal_id,
            "added": report.added,
            "updated": report.updated,
            "removed": report.removed,
            "links_added": report.links_added,
            "links_removed": report.links_removed,
            "record_path": str(report.record_path.relative_to(project_root)),
        }
    }


def apply_shape(
    graph: IntentGraph, project_root: Path, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    outcome = graph.get_node(required_string(arguments, "outcome_id"))
    if outcome.type != NodeType.OUTCOME.value:
        raise AgentProtocolError(
            "invalid_arguments", "arguments.outcome_id must identify an outcome node."
        )
    policy_name = optional_string(arguments, "policy")
    policy = PolicyRegistry.from_project(project_root).resolve(policy_name) if policy_name else None
    risk = optional_risk(arguments, "risk") or (policy.risk if policy else "R1")
    evaluation = optional_evaluation(arguments, "proof_evaluation") or (
        policy.evaluation if policy else "latest"
    )
    required_checkers = string_list(arguments, "required_checkers") or (
        list(policy.required_checkers) if policy else []
    )
    requirement_properties: dict[str, Any] = {"risk": risk}
    if policy:
        requirement_properties["policy_pack"] = policy.to_properties()
    requirement = graph.add_node(
        NodeType.REQUIREMENT,
        required_string(arguments, "title"),
        required_string(arguments, "description"),
        status=NodeStatus.ACTIVE,
        properties=requirement_properties,
    )
    graph.add_edge(requirement.id, outcome.id, RelationType.DERIVES_FROM)
    created: list[Node] = [requirement]
    decision_title = optional_string(arguments, "decision_title")
    rationale = optional_string(arguments, "rationale")
    alternatives = string_list(arguments, "alternatives")
    if decision_title or rationale or alternatives:
        if not decision_title or not rationale:
            raise AgentProtocolError(
                "invalid_arguments",
                "decision_title and rationale are both required when adding a decision.",
            )
        decision = graph.add_node(
            NodeType.DECISION,
            decision_title,
            rationale,
            status=NodeStatus.PROPOSED,
            properties={"alternatives": alternatives},
        )
        graph.add_edge(decision.id, requirement.id, RelationType.ADDRESSES)
        created.append(decision)
    proof_title = optional_string(arguments, "proof_title")
    proof_description = optional_string(arguments, "proof_description")
    if policy and policy.proof_required and not proof_title and not proof_description:
        proof_title = policy.proof_title(requirement.title)
        proof_description = policy.proof_description(requirement.title)
    if proof_title or proof_description:
        if not proof_title or not proof_description:
            raise AgentProtocolError(
                "invalid_arguments",
                "proof_title and proof_description are both required when adding a proof.",
            )
        proof_properties: dict[str, Any] = {
            "risk": risk,
            "checker_kind": optional_string(arguments, "proof_checker_kind"),
            "evaluation": evaluation,
            "required_checkers": required_checkers,
        }
        if policy:
            proof_properties["policy_pack"] = policy.to_properties()
        proof = graph.add_node(
            NodeType.PROOF_OBLIGATION,
            proof_title,
            proof_description,
            status=NodeStatus.PLANNED,
            properties=proof_properties,
        )
        graph.add_edge(requirement.id, proof.id, RelationType.REQUIRES_PROOF)
        created.append(proof)
    return {"created": [node_to_dict(node) for node in created]}


def apply_prove(graph: IntentGraph, arguments: Mapping[str, Any]) -> dict[str, Any]:
    obligation = graph.get_node(required_string(arguments, "obligation_id"))
    if obligation.type != NodeType.PROOF_OBLIGATION.value:
        raise AgentProtocolError(
            "invalid_arguments", "arguments.obligation_id must identify a proof obligation."
        )
    result = optional_evidence_result(arguments)
    evidence_status = {
        "pass": NodeStatus.VERIFIED,
        "fail": NodeStatus.FAILED,
        "recorded": NodeStatus.ACTIVE,
    }[result]
    evidence = graph.add_node(
        NodeType.EVIDENCE,
        required_string(arguments, "title"),
        required_string(arguments, "description"),
        status=evidence_status,
        properties={"source": required_string(arguments, "source"), "result": result},
    )
    graph.add_edge(evidence.id, obligation.id, RelationType.PROVES)
    evaluation = obligation.properties.get("evaluation", "latest")
    if evaluation == "manual":
        graph.set_status(obligation.id, evidence_status)
    else:
        graph.set_status(obligation.id, aggregate_obligation_status(graph, obligation.id))
    return {
        "created": [node_to_dict(evidence)],
        "proof_status": graph.get_node(obligation.id).status,
    }


def optional_string(
    arguments: Mapping[str, Any], key: str, default: str | None = None
) -> str | None:
    value = arguments.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentProtocolError(
            "invalid_arguments", f"arguments.{key} must be a non-empty string."
        )
    return value.strip()


def required_project_directory(project_root: Path, arguments: Mapping[str, Any], key: str) -> Path:
    path = optional_project_path(project_root, arguments, key)
    if path is None or not path.is_dir():
        raise AgentProtocolError(
            "invalid_arguments", f"arguments.{key} must identify a project-contained directory."
        )
    return path


def required_content(arguments: Mapping[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise AgentProtocolError("invalid_arguments", f"arguments.{key} must be a string.")
    return value


def string_list(arguments: Mapping[str, Any], key: str) -> list[str]:
    value = arguments.get(key, [])
    valid_items = isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    )
    if not valid_items:
        raise AgentProtocolError("invalid_arguments", f"arguments.{key} must be a list of strings.")
    return [item.strip() for item in value]


def required_object(
    arguments: Mapping[str, Any], key: str, *, default: dict[str, Any]
) -> dict[str, Any]:
    value = arguments.get(key, default)
    if not isinstance(value, dict):
        raise AgentProtocolError("invalid_arguments", f"arguments.{key} must be a JSON object.")
    return value


def optional_risk(arguments: Mapping[str, Any], key: str) -> str | None:
    value = optional_string(arguments, key)
    if value is not None and value not in {"R0", "R1", "R2", "R3"}:
        raise AgentProtocolError(
            "invalid_arguments", f"arguments.{key} must be one of R0, R1, R2, R3."
        )
    return value


def optional_evaluation(arguments: Mapping[str, Any], key: str) -> str | None:
    value = optional_string(arguments, key)
    if value is not None and value not in {"latest", "all", "any", "manual"}:
        raise AgentProtocolError(
            "invalid_arguments", f"arguments.{key} must be latest, all, any, or manual."
        )
    return value


def optional_evidence_result(arguments: Mapping[str, Any]) -> str:
    value = optional_string(arguments, "result", default="recorded")
    if value not in {"pass", "fail", "recorded"}:
        raise AgentProtocolError(
            "invalid_arguments", "arguments.result must be pass, fail, or recorded."
        )
    return value
