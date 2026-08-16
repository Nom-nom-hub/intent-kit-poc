"""Command-line interface for the Intent Kit proof of concept."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .kernel import GraphStore, NodeStatus, NodeType, RelationType
from .proof_checkers import CheckerRegistry, CheckState, ProofRunner
from .proof_checkers.builtin import FileExistsChecker
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
        default="R1",
        help="Risk class used to calibrate proof.",
    )
    shape.add_argument("--decision-title", help="Optional implementation decision title.")
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
        default="latest",
        help="Evidence aggregation policy for the proof.",
    )
    shape.add_argument(
        "--required-checker",
        action="append",
        default=[],
        help="Checker ID required by all/any policies. Repeatable.",
    )
    shape.set_defaults(handler=handle_shape)

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


def handle_shape(args: argparse.Namespace) -> int:
    store = load_store(args.path)
    graph = store.load()
    outcome = graph.get_node(args.outcome)
    if outcome.type != NodeType.OUTCOME.value:
        raise ValueError(f"{args.outcome} is a {outcome.type}, not an outcome.")

    requirement = graph.add_node(
        NodeType.REQUIREMENT,
        args.title,
        args.description,
        status=NodeStatus.ACTIVE,
        properties={"risk": args.risk},
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

    if args.proof_title or args.proof_description:
        if not args.proof_title or not args.proof_description:
            raise ValueError(
                "A proof obligation requires both --proof-title and --proof-description."
            )
        proof = graph.add_node(
            NodeType.PROOF_OBLIGATION,
            args.proof_title,
            args.proof_description,
            status=NodeStatus.PLANNED,
            properties={
                "risk": args.risk,
                "checker_kind": args.proof_checker_kind,
                "evaluation": args.proof_evaluation,
                "required_checkers": args.required_checker,
            },
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
    graph.set_status(
        obligation.id,
        NodeStatus.VERIFIED
        if args.result == "pass"
        else NodeStatus.FAILED
        if args.result == "fail"
        else NodeStatus.ACTIVE,
    )
    store.save(graph)
    MarkdownRenderer(args.path).render(graph)
    print(f"Recorded {evidence.id} against {obligation.id}: {args.result}")
    return 0


def handle_check(args: argparse.Namespace) -> int:
    config = parse_checker_config(args.config)
    result = ProofRunner(load_store(args.path), default_registry()).run(
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


def default_registry() -> CheckerRegistry:
    registry = CheckerRegistry()
    registry.register(FileExistsChecker())
    return registry


def parse_checker_config(raw_config: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Checker configuration must be valid JSON: {exc.msg}.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Checker configuration must be a JSON object.")
    return parsed


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
