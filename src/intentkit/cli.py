"""Command-line interface for the Intent Kit proof of concept."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .agent_protocol import (
    COMPUTER_READ_OPERATIONS,
    COMPUTER_RUN_OPERATIONS,
    MUTATION_OPERATIONS,
    READ_OPERATIONS,
    AgentProtocolError,
    error_response,
    execute_computer,
    execute_mutation,
    execute_read,
    parse_request,
)
from .importers import SpecKitImporter
from .insights import (
    DriftStatus,
    analyze_impact,
    render_drift,
    render_impact,
    scan_drift,
    source_nodes,
)
from .kernel import GraphStore, NodeStatus, NodeType, RelationType
from .policies import PolicyRegistry, render_policy_list, render_policy_show
from .proof_checkers import CheckerRegistry, CheckState, ProofRunner
from .proof_checkers.builtin import FileExistsChecker
from .proof_checkers.external import ExternalCheckerRegistry
from .proof_checkers.runner import aggregate_obligation_status
from .renderer import MarkdownRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intentkit",
        description="A local-first proof of concept for Intent Graph Development.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize Intent Kit in a project directory.")
    add_path(init)
    init.add_argument(
        "--project-name", help="Human-readable project name. Defaults to the directory name."
    )
    init.set_defaults(handler=handle_init)

    capture = subparsers.add_parser("capture", help="Capture an outcome and its measurable intent.")
    add_path(capture)
    capture.add_argument("title", help="Short outcome title.")
    capture.add_argument(
        "--description", required=True, help="Why the outcome matters and what should change."
    )
    capture.add_argument(
        "--success-measure",
        action="append",
        default=[],
        help="Measurable success criterion. Repeatable.",
    )
    capture.add_argument(
        "--assumption", action="append", default=[], help="Key assumption. Repeatable."
    )
    capture.set_defaults(handler=handle_capture)

    shape = subparsers.add_parser(
        "shape", help="Add a requirement, decision, and proof obligation for an outcome."
    )
    add_path(shape)
    shape.add_argument("title", help="Short requirement title.")
    shape.add_argument("--description", required=True, help="Testable requirement statement.")
    shape.add_argument("--outcome", required=True, help="Outcome ID the requirement derives from.")
    shape.add_argument(
        "--risk",
        choices=["R0", "R1", "R2", "R3"],
        default=None,
        help="Risk class used to calibrate proof.",
    )
    shape.add_argument("--decision-title", help="Optional implementation decision title.")
    shape.add_argument(
        "--policy",
        help=(
            "Optional policy pack. It supplies risk and proof defaults without overriding "
            "explicit flags."
        ),
    )
    shape.add_argument("--rationale", help="Rationale for the optional decision.")
    shape.add_argument(
        "--alternative", action="append", default=[], help="Alternative considered. Repeatable."
    )
    shape.add_argument("--proof-title", help="Optional proof obligation title.")
    shape.add_argument(
        "--proof-description", help="Claim that the proof obligation must demonstrate."
    )
    shape.add_argument(
        "--proof-checker-kind",
        help="Optional checker kind required by the proof, e.g. file_exists.",
    )
    shape.add_argument(
        "--proof-evaluation",
        choices=["latest", "all", "any", "manual"],
        default=None,
        help="Evidence aggregation policy for the proof.",
    )
    shape.add_argument(
        "--required-checker",
        action="append",
        default=[],
        help="Checker ID required by all/any policies. Repeatable.",
    )
    shape.set_defaults(handler=handle_shape)

    policy = subparsers.add_parser(
        "policy", help="List, inspect, or initialize local risk-calibrated policy packs."
    )
    add_path(policy)
    policy.add_argument("action", choices=["list", "show", "init"])
    policy.add_argument("name", nargs="?", help="Policy pack name required by 'show'.")
    policy.set_defaults(handler=handle_policy)

    checker = subparsers.add_parser(
        "checker", help="Initialize or inspect the controlled proof-checker allowlist."
    )
    add_path(checker)
    checker.add_argument("action", choices=["list", "init"])
    checker.set_defaults(handler=handle_checker)

    prove = subparsers.add_parser("prove", help="Record evidence against a proof obligation.")
    add_path(prove)
    prove.add_argument("obligation", help="Proof obligation ID.")
    prove.add_argument("title", help="Short evidence title.")
    prove.add_argument("--description", required=True, help="What was executed or observed.")
    prove.add_argument(
        "--source", required=True, help="Source path, CI job, review, or external reference."
    )
    prove.add_argument(
        "--result",
        choices=["pass", "fail", "recorded"],
        default="recorded",
        help="Evidence result.",
    )
    prove.set_defaults(handler=handle_prove)

    check = subparsers.add_parser(
        "check", help="Run a trusted proof checker and record its evidence."
    )
    add_path(check)
    check.add_argument("obligation", help="Proof obligation ID.")
    check.add_argument(
        "--checker", required=True, help="Registered checker ID, e.g. local.file-exists."
    )
    check.add_argument("--config", default="{}", help="Checker configuration as a JSON object.")
    check.set_defaults(handler=handle_check)

    import_speckit = subparsers.add_parser(
        "import-speckit", help="Import a completed Spec Kit feature directory with provenance."
    )
    add_path(import_speckit)
    import_speckit.add_argument(
        "source", type=Path, help="Spec Kit feature directory containing spec.md."
    )
    import_speckit.set_defaults(handler=handle_import_speckit)

    drift = subparsers.add_parser(
        "drift", help="Compare imported source artifacts with recorded provenance."
    )
    add_path(drift)
    drift.add_argument(
        "--source",
        type=Path,
        help="Optional imported feature directory or source artifact to scan.",
    )
    drift.set_defaults(handler=handle_drift)

    impact = subparsers.add_parser(
        "impact", help="Show typed graph paths and proof gaps affected by a node or source."
    )
    add_path(impact)
    impact.add_argument("node", nargs="?", help="Graph node ID to analyze.")
    impact.add_argument(
        "--source",
        type=Path,
        help="Imported feature directory or source artifact whose nodes to analyze.",
    )
    impact.add_argument(
        "--proof-gaps",
        action="store_true",
        help="Return a nonzero status when affected proof obligations are not verified.",
    )
    impact.set_defaults(handler=handle_impact)

    agent = subparsers.add_parser(
        "agent", help="Serve a strict JSON protocol for controlled agent access to this project."
    )
    add_path(agent)
    request_source = agent.add_mutually_exclusive_group(required=True)
    request_source.add_argument("--request", help="Agent request as a JSON object.")
    request_source.add_argument(
        "--request-file", type=Path, help="Path to an agent JSON request file."
    )
    agent.add_argument(
        "--apply",
        action="store_true",
        help="Required for supported mutation operations; read operations never mutate.",
    )
    agent.set_defaults(handler=handle_agent)

    render = subparsers.add_parser("render", help="Regenerate Markdown views from the graph.")
    add_path(render)
    render.set_defaults(handler=handle_render)

    status = subparsers.add_parser("status", help="Show graph and proof coverage summary.")
    add_path(status)
    status.set_defaults(handler=handle_status)
    return parser


def add_path(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--path",
        default=".",
        type=Path,
        help="Project directory. Defaults to the current directory.",
    )


def handle_init(args: argparse.Namespace) -> int:
    root = args.path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    store = GraphStore(root)
    graph = store.initialize(args.project_name or root.name)
    MarkdownRenderer(root).render(graph)
    print(f"Initialized Intent Kit in {root}")
    print('Next: intentkit capture "Your outcome" --description "Why it matters"')
    return 0


def handle_capture(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    outcome = graph.add_node(
        NodeType.OUTCOME,
        args.title,
        args.description,
        status=NodeStatus.ACTIVE,
        properties={"success_measures": args.success_measure, "assumptions": args.assumption},
    )
    store.save(graph)
    MarkdownRenderer(args.path).render(graph)
    print(f"Captured {outcome.id}: {outcome.title}")
    return 0


def handle_checker(args: argparse.Namespace) -> int:
    external = ExternalCheckerRegistry(args.path.resolve())
    if args.action == "init":
        path = external.write_template()
        print(f"Created external checker allowlist: {path}")
        return 0
    external_ids = {checker.descriptor.checker_id for checker in external.load()}
    print("Available proof checkers:")
    for descriptor in default_registry(args.path).descriptors():
        origin = "external" if descriptor.checker_id in external_ids else "built-in"
        kinds = ", ".join(descriptor.supported_kinds) or "any configured proof kind"
        print(
            f"- {descriptor.checker_id}@{descriptor.version} [{origin}] "
            f"— {descriptor.display_name}; kinds: {kinds}"
        )
    return 0


def handle_policy(args: argparse.Namespace) -> int:
    registry = PolicyRegistry.from_project(args.path.resolve())
    if args.action == "init":
        path = registry.write_template()
        print(f"Created policy configuration: {path}")
        return 0
    if args.action == "list":
        print(render_policy_list(registry))
        return 0
    if not args.name:
        raise ValueError("'intentkit policy show' requires a policy pack name.")
    print(render_policy_show(registry.resolve(args.name)))
    return 0


def handle_shape(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    outcome = graph.get_node(args.outcome)
    if outcome.type != NodeType.OUTCOME.value:
        raise ValueError(f"{args.outcome} is a {outcome.type}, not an outcome.")

    registry = PolicyRegistry.from_project(args.path.resolve())
    policy = registry.resolve(args.policy) if args.policy else None
    risk = args.risk or (policy.risk if policy else "R1")
    evaluation = args.proof_evaluation or (policy.evaluation if policy else "latest")
    required_checkers = args.required_checker or (list(policy.required_checkers) if policy else [])
    requirement_properties: dict[str, Any] = {"risk": risk}
    if policy:
        requirement_properties["policy_pack"] = policy.to_properties()
    requirement = graph.add_node(
        NodeType.REQUIREMENT,
        args.title,
        args.description,
        status=NodeStatus.ACTIVE,
        properties=requirement_properties,
    )
    graph.add_edge(requirement.id, outcome.id, RelationType.DERIVES_FROM)
    recorded = [requirement.id]

    if args.decision_title or args.rationale or args.alternative:
        if not args.decision_title or not args.rationale:
            raise ValueError("A decision requires both --decision-title and --rationale.")
        decision = graph.add_node(
            NodeType.DECISION,
            args.decision_title,
            args.rationale,
            status=NodeStatus.PROPOSED,
            properties={"alternatives": args.alternative},
        )
        graph.add_edge(decision.id, requirement.id, RelationType.ADDRESSES)
        recorded.append(decision.id)

    proof_title = args.proof_title
    proof_description = args.proof_description
    if policy and policy.proof_required and not proof_title and not proof_description:
        proof_title = policy.proof_title(args.title)
        proof_description = policy.proof_description(args.title)
    if proof_title or proof_description:
        if not proof_title or not proof_description:
            raise ValueError(
                "A proof obligation requires both --proof-title and --proof-description."
            )
        proof_properties: dict[str, Any] = {
            "risk": risk,
            "checker_kind": args.proof_checker_kind,
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
        recorded.append(proof.id)

    store.save(graph)
    MarkdownRenderer(args.path).render(graph)
    print("Shaped " + ", ".join(recorded))
    return 0


def handle_prove(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    obligation = graph.get_node(args.obligation)
    if obligation.type != NodeType.PROOF_OBLIGATION.value:
        raise ValueError(f"{args.obligation} is a {obligation.type}, not a proof obligation.")
    evidence_status = (
        NodeStatus.VERIFIED
        if args.result == "pass"
        else NodeStatus.FAILED
        if args.result == "fail"
        else NodeStatus.ACTIVE
    )
    evidence = graph.add_node(
        NodeType.EVIDENCE,
        args.title,
        args.description,
        status=evidence_status,
        properties={"source": args.source, "result": args.result},
    )
    graph.add_edge(evidence.id, obligation.id, RelationType.PROVES)
    evaluation = obligation.properties.get("evaluation", "latest")
    if evaluation == "manual":
        graph.set_status(
            obligation.id,
            NodeStatus.VERIFIED
            if args.result == "pass"
            else NodeStatus.FAILED
            if args.result == "fail"
            else NodeStatus.ACTIVE,
        )
    else:
        graph.set_status(obligation.id, aggregate_obligation_status(graph, obligation.id))
    store.save(graph)
    MarkdownRenderer(args.path).render(graph)
    print(f"Recorded {evidence.id} against {obligation.id}: {args.result}")
    return 0


def handle_check(args: argparse.Namespace) -> int:
    config = parse_checker_config(args.config)
    result = ProofRunner(load_store(args.path), default_registry(args.path)).run(
        args.obligation,
        args.checker,
        config,
    )
    print(f"{result.state.value.upper()}: {result.summary}")
    return {
        CheckState.PASS: 0,
        CheckState.SKIPPED: 0,
        CheckState.FAIL: 1,
        CheckState.INCONCLUSIVE: 2,
        CheckState.ERROR: 3,
    }[result.state]


def default_registry(project_root: Path) -> CheckerRegistry:
    registry = CheckerRegistry()
    registry.register(FileExistsChecker())
    for checker in ExternalCheckerRegistry(project_root).load():
        registry.register(checker)
    return registry


def parse_checker_config(raw_config: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Checker configuration must be valid JSON: {exc.msg}.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Checker configuration must be a JSON object.")
    return parsed


def handle_drift(args: argparse.Namespace) -> int:
    records = scan_drift(load_store(args.path).load(), args.source)
    print(render_drift(records))
    degraded = {DriftStatus.CHANGED, DriftStatus.MISSING, DriftStatus.UNSUPPORTED}
    return 1 if any(record.status in degraded for record in records) else 0


def handle_impact(args: argparse.Namespace) -> int:
    if bool(args.node) == bool(args.source):
        raise ValueError("Provide exactly one impact target: NODE or --source PATH.")
    graph = load_store(args.path).load()
    targets = [graph.get_node(args.node)] if args.node else source_nodes(graph, args.source)
    if not targets:
        print("No graph nodes matched the requested source.")
        return 0
    reports = [analyze_impact(graph, target.id) for target in targets]
    print("\n\n".join(render_impact(report) for report in reports))
    if args.proof_gaps and any(report.proof_gaps for report in reports):
        return 1
    return 0


def handle_agent(args: argparse.Namespace) -> int:
    raw_request = (
        args.request_file.read_text(encoding="utf-8") if args.request_file else args.request
    )
    request_id: str | None = None
    try:
        request = parse_request(raw_request)
        request_id = request["request_id"]
        project_root = args.path.resolve()
        checker_registry = default_registry(project_root)
        operation = request["operation"]
        if operation in READ_OPERATIONS:
            response = execute_read(project_root, request, checker_registry.descriptors())
        elif operation in COMPUTER_READ_OPERATIONS | COMPUTER_RUN_OPERATIONS:
            response = execute_computer(project_root, request, apply=args.apply)
        elif operation in MUTATION_OPERATIONS:
            response = execute_mutation(
                project_root,
                request,
                checker_registry,
                apply=args.apply,
            )
        else:
            raise AgentProtocolError("unsupported_operation", f"Unsupported operation: {operation}")
        exit_code = 0
    except AgentProtocolError as exc:
        response = error_response(request_id, exc.code, str(exc))
        exit_code = 2
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        response = error_response(request_id, "project_error", str(exc))
        exit_code = 2
    print(json.dumps(response, sort_keys=True))
    return exit_code


def handle_import_speckit(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    report = SpecKitImporter(args.source).import_into(graph)
    store.save(graph)
    MarkdownRenderer(args.path).render(graph)
    print(
        "Imported Spec Kit feature into "
        f"{report.feature_outcome_id}: {report.user_stories} user stories, "
        f"{report.functional_requirements} functional requirements, "
        f"{report.decisions} plan decisions, and {report.tasks} tasks."
    )
    return 0


def handle_render(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    paths = MarkdownRenderer(args.path).render(store.load())
    print("Rendered " + ", ".join(str(path.relative_to(args.path.resolve())) for path in paths))
    return 0


def handle_status(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    counts = {node_type.value: 0 for node_type in NodeType}
    for node in graph.nodes.values():
        counts[node.type] += 1
    obligations = [
        node for node in graph.nodes.values() if node.type == NodeType.PROOF_OBLIGATION.value
    ]
    verified = [node for node in obligations if node.status == NodeStatus.VERIFIED.value]
    failed = [node for node in obligations if node.status == NodeStatus.FAILED.value]
    print(f"Project: {graph.project_name}")
    print(f"Nodes: {len(graph.nodes)} | Edges: {len(graph.edges)}")
    print(" | ".join(f"{label}: {count}" for label, count in counts.items() if count))
    print(f"Proof coverage: {len(verified)}/{len(obligations)} verified | {len(failed)} failed")
    applied_policies: dict[str, int] = {}
    requirements = [
        node for node in graph.nodes.values() if node.type == NodeType.REQUIREMENT.value
    ]
    for requirement in requirements:
        policy = requirement.properties.get("policy_pack")
        if isinstance(policy, dict) and isinstance(policy.get("name"), str):
            name = policy["name"]
            applied_policies[name] = applied_policies.get(name, 0) + 1
    if applied_policies:
        summary = ", ".join(f"{name}: {count}" for name, count in sorted(applied_policies.items()))
        print(f"Policy packs: {summary}")
    return 0


def load_store(path: Path) -> GraphStore:
    return GraphStore(path.resolve())


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
