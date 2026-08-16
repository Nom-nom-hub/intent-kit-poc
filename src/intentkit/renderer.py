"""Markdown projections for the Intent Kit graph.

Generated sections are deterministic. A clearly marked manual-notes section survives
subsequent renders, making the documents useful in normal Git review workflows.
"""

from __future__ import annotations

from pathlib import Path

from .kernel import Edge, GraphStore, IntentGraph, Node, NodeType, RelationType

MANUAL_START = "<!-- intentkit:manual-notes:start -->"
MANUAL_END = "<!-- intentkit:manual-notes:end -->"


class MarkdownRenderer:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.output_dir = self.project_root / "intent"

    def render(self, graph: IntentGraph) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "intent.md": self._render_intent(graph),
            "design.md": self._render_design(graph),
            "evidence.md": self._render_evidence(graph),
            "traceability.md": self._render_traceability(graph),
        }
        written: list[Path] = []
        for filename, content in paths.items():
            path = self.output_dir / filename
            path.write_text(self._with_manual_notes(path, content), encoding="utf-8")
            written.append(path)
        return written

    def _render_intent(self, graph: IntentGraph) -> str:
        outcomes = nodes_of_type(graph, NodeType.OUTCOME)
        requirements = nodes_of_type(graph, NodeType.REQUIREMENT)
        lines = [
            "# Intent Contract",
            "",
            f"**Project:** {graph.project_name}",
            f"**Graph updated:** {graph.updated_at}",
            "",
            "## Outcomes",
            "",
        ]
        lines.extend(render_node_list(outcomes, fallback="No outcomes have been captured yet."))
        lines += ["", "## Requirements", ""]
        if not requirements:
            lines.append("No requirements have been shaped yet.")
        else:
            for requirement in requirements:
                outcome_titles = related_titles(
                    graph, requirement.id, RelationType.DERIVES_FROM, outgoing=True
                )
                origin = f" Derived from: {', '.join(outcome_titles)}." if outcome_titles else ""
                lines.append(
                    f"- **{requirement.id} — {requirement.title}** (`{requirement.status}`): "
                    f"{requirement.description}{origin}"
                )
        return "\n".join(lines) + "\n"

    def _render_design(self, graph: IntentGraph) -> str:
        decisions = nodes_of_type(graph, NodeType.DECISION)
        requirements = nodes_of_type(graph, NodeType.REQUIREMENT)
        tasks = nodes_of_type(graph, NodeType.IMPLEMENTATION_TASK)
        lines = [
            "# Design and Decision Record",
            "",
            f"**Project:** {graph.project_name}",
            "",
            "## Active Requirements",
            "",
        ]
        lines.extend(
            render_node_list(
                requirements, fallback="Capture and shape a requirement to begin design work."
            )
        )
        lines += ["", "## Decisions", ""]
        if not decisions:
            lines.append("No decisions have been recorded yet.")
        else:
            for decision in decisions:
                requirement_titles = related_titles(
                    graph, decision.id, RelationType.ADDRESSES, outgoing=True
                )
                alternatives = decision.properties.get("alternatives", [])
                lines.append(f"### {decision.id} — {decision.title}")
                lines.append("")
                lines.append(f"**Status:** `{decision.status}`")
                lines.append(f"**Rationale:** {decision.description}")
                if requirement_titles:
                    lines.append(f"**Addresses:** {', '.join(requirement_titles)}")
                if alternatives:
                    lines.append(f"**Alternatives considered:** {', '.join(alternatives)}")
                lines.append("")
        lines += ["## Implementation Tasks", ""]
        if not tasks:
            lines.append("No implementation tasks have been imported or recorded yet.")
        else:
            for task in tasks:
                phase = task.properties.get("phase")
                story = task.properties.get("story_label")
                labels = ", ".join(label for label in [phase, story] if label)
                implements = related_titles(graph, task.id, RelationType.IMPLEMENTS, outgoing=True)
                suffix = f" ({labels})" if labels else ""
                lines.append(
                    f"- **{task.id} — {task.title}** (`{task.status}`){suffix}: {task.description}"
                )
                if implements:
                    lines.append(f"  - Implements: {', '.join(implements)}")
        return "\n".join(lines).rstrip() + "\n"

    def _render_evidence(self, graph: IntentGraph) -> str:
        obligations = nodes_of_type(graph, NodeType.PROOF_OBLIGATION)
        lines = [
            "# Evidence Register",
            "",
            f"**Project:** {graph.project_name}",
            "",
            "## Proof Obligations",
            "",
        ]
        if not obligations:
            lines.append("No proof obligations have been added yet.")
        else:
            for obligation in obligations:
                evidence_edges = graph.incoming(obligation.id, RelationType.PROVES)
                evidence_nodes = [graph.get_node(edge.source) for edge in evidence_edges]
                lines.append(f"### {obligation.id} — {obligation.title}")
                lines.append("")
                lines.append(f"**Status:** `{obligation.status}`")
                lines.append(f"**Claim:** {obligation.description}")
                lines.append("**Evidence:**")
                if evidence_nodes:
                    for evidence in evidence_nodes:
                        result = evidence.properties.get("result", "recorded")
                        source = evidence.properties.get("source", "unspecified")
                        lines.append(
                            f"- `{result}` — **{evidence.id}**: {evidence.title} (source: {source})"
                        )
                else:
                    lines.append("- _No evidence recorded._")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_traceability(self, graph: IntentGraph) -> str:
        lines = [
            "# Traceability Map",
            "",
            "| Source | Relation | Target |",
            "|---|---|---|",
        ]
        if not graph.edges:
            lines.append("| _No links recorded_ | — | — |")
        else:
            for edge in sorted(
                graph.edges.values(), key=lambda item: (item.source, item.relation, item.target)
            ):
                source = graph.get_node(edge.source)
                target = graph.get_node(edge.target)
                lines.append(
                    "| "
                    f"{source.id} — {source.title} | `{edge.relation}` | "
                    f"{target.id} — {target.title} |"
                )
        return "\n".join(lines) + "\n"

    def _with_manual_notes(self, path: Path, content: str) -> str:
        manual_notes = self._extract_manual_notes(path)
        return (
            content.rstrip()
            + "\n\n## Manual Notes\n\n"
            + MANUAL_START
            + "\n"
            + manual_notes.rstrip()
            + "\n"
            + MANUAL_END
            + "\n"
        )

    @staticmethod
    def _extract_manual_notes(path: Path) -> str:
        if not path.exists():
            return (
                "Add team context, review notes, or links here. "
                "This section is preserved on re-render."
            )
        content = path.read_text(encoding="utf-8")
        if MANUAL_START not in content or MANUAL_END not in content:
            return (
                "Existing document did not contain Intent Kit markers; "
                "preserve any important notes before the next render."
            )
        return content.split(MANUAL_START, 1)[1].split(MANUAL_END, 1)[0].strip()


def nodes_of_type(graph: IntentGraph, node_type: NodeType) -> list[Node]:
    return sorted(
        (node for node in graph.nodes.values() if node.type == node_type.value),
        key=lambda node: node.id,
    )


def render_node_list(nodes: list[Node], fallback: str) -> list[str]:
    if not nodes:
        return [fallback]
    return [
        f"- **{node.id} — {node.title}** (`{node.status}`): {node.description}" for node in nodes
    ]


def related_titles(
    graph: IntentGraph, node_id: str, relation: RelationType, *, outgoing: bool
) -> list[str]:
    edges: list[Edge] = (
        graph.outgoing(node_id, relation) if outgoing else graph.incoming(node_id, relation)
    )
    related_nodes = [graph.get_node(edge.target if outgoing else edge.source) for edge in edges]
    return [f"{node.id} — {node.title}" for node in related_nodes]


def render_project(project_root: Path) -> list[Path]:
    store = GraphStore(project_root)
    return MarkdownRenderer(project_root).render(store.load())
