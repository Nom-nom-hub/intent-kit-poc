"""Local-first graph kernel for the Intent Kit proof of concept."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


GRAPH_SCHEMA_VERSION = "0.1"


class NodeType(StrEnum):
    OUTCOME = "outcome"
    REQUIREMENT = "requirement"
    DECISION = "decision"
    PROOF_OBLIGATION = "proof_obligation"
    EVIDENCE = "evidence"
    OBSERVED_BEHAVIOR = "observed_behavior"


class NodeStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PROPOSED = "proposed"
    PLANNED = "planned"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class RelationType(StrEnum):
    DERIVES_FROM = "derives_from"
    SATISFIES = "satisfies"
    CONSTRAINS = "constrains"
    ADDRESSES = "addresses"
    IMPLEMENTS = "implements"
    REQUIRES_PROOF = "requires_proof"
    PROVES = "proves"
    OBSERVES = "observes"


@dataclass(slots=True)
class Node:
    """An addressable entity in the intent graph."""

    id: str
    type: str
    title: str
    description: str
    status: str
    created_at: str
    updated_at: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    """A typed directed connection between two existing graph nodes."""

    id: str
    source: str
    target: str
    relation: str
    created_at: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IntentGraph:
    """Serializable local graph with light-weight integrity constraints."""

    schema_version: str = GRAPH_SCHEMA_VERSION
    project_name: str = ""
    created_at: str = field(default_factory=lambda: utc_now())
    updated_at: str = field(default_factory=lambda: utc_now())
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)

    def add_node(
        self,
        node_type: NodeType | str,
        title: str,
        description: str,
        *,
        status: NodeStatus | str = NodeStatus.DRAFT,
        properties: dict[str, Any] | None = None,
    ) -> Node:
        type_value = NodeType(node_type).value
        status_value = NodeStatus(status).value
        now = utc_now()
        node = Node(
            id=next_node_id(type_value, self.nodes),
            type=type_value,
            title=title.strip(),
            description=description.strip(),
            status=status_value,
            created_at=now,
            updated_at=now,
            properties=dict(properties or {}),
        )
        if not node.title:
            raise ValueError("A graph node requires a non-empty title.")
        self.nodes[node.id] = node
        self.touch()
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        relation: RelationType | str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> Edge:
        if source not in self.nodes:
            raise ValueError(f"Unknown source node: {source}")
        if target not in self.nodes:
            raise ValueError(f"Unknown target node: {target}")
        if source == target:
            raise ValueError("Self-referential edges are not allowed in this POC.")
        relation_value = RelationType(relation).value
        if any(
            edge.source == source and edge.target == target and edge.relation == relation_value
            for edge in self.edges.values()
        ):
            raise ValueError(f"Duplicate edge: {source} -[{relation_value}]-> {target}")
        edge = Edge(
            id=f"edge-{uuid4().hex[:12]}",
            source=source,
            target=target,
            relation=relation_value,
            created_at=utc_now(),
            properties=dict(properties or {}),
        )
        self.edges[edge.id] = edge
        self.touch()
        return edge

    def get_node(self, node_id: str) -> Node:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise ValueError(f"Unknown graph node: {node_id}") from exc

    def set_status(self, node_id: str, status: NodeStatus | str) -> Node:
        node = self.get_node(node_id)
        node.status = NodeStatus(status).value
        node.updated_at = utc_now()
        self.touch()
        return node

    def incoming(self, node_id: str, relation: RelationType | str | None = None) -> list[Edge]:
        relation_value = RelationType(relation).value if relation else None
        return [
            edge
            for edge in self.edges.values()
            if edge.target == node_id and (relation_value is None or edge.relation == relation_value)
        ]

    def outgoing(self, node_id: str, relation: RelationType | str | None = None) -> list[Edge]:
        relation_value = RelationType(relation).value if relation else None
        return [
            edge
            for edge in self.edges.values()
            if edge.source == node_id and (relation_value is None or edge.relation == relation_value)
        ]

    def validate(self) -> list[str]:
        errors: list[str] = []
        for edge in self.edges.values():
            if edge.source not in self.nodes:
                errors.append(f"{edge.id} has a missing source: {edge.source}")
            if edge.target not in self.nodes:
                errors.append(f"{edge.id} has a missing target: {edge.target}")
            if edge.source == edge.target:
                errors.append(f"{edge.id} is self-referential")
        for node in self.nodes.values():
            if not node.title.strip():
                errors.append(f"{node.id} has no title")
        return errors

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_name": self.project_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": {node_id: asdict(node) for node_id, node in self.nodes.items()},
            "edges": {edge_id: asdict(edge) for edge_id, edge in self.edges.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IntentGraph":
        graph = cls(
            schema_version=payload.get("schema_version", GRAPH_SCHEMA_VERSION),
            project_name=payload.get("project_name", ""),
            created_at=payload.get("created_at", utc_now()),
            updated_at=payload.get("updated_at", utc_now()),
            nodes={node_id: Node(**node) for node_id, node in payload.get("nodes", {}).items()},
            edges={edge_id: Edge(**edge) for edge_id, edge in payload.get("edges", {}).items()},
        )
        errors = graph.validate()
        if errors:
            raise ValueError("Invalid intent graph: " + "; ".join(errors))
        return graph


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def next_node_id(node_type: str, nodes: dict[str, Node]) -> str:
    prefix = {
        NodeType.OUTCOME.value: "OUT",
        NodeType.REQUIREMENT.value: "REQ",
        NodeType.DECISION.value: "DEC",
        NodeType.PROOF_OBLIGATION.value: "PRF",
        NodeType.EVIDENCE.value: "EVD",
        NodeType.OBSERVED_BEHAVIOR.value: "OBS",
    }[node_type]
    current_ids = [node_id for node_id in nodes if node_id.startswith(f"{prefix}-")]
    numbers = [int(node_id.split("-")[1]) for node_id in current_ids if node_id.split("-")[1].isdigit()]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


class GraphStore:
    """A small durable store. JSON is canonical and Git-friendly for the POC."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.intent_dir = self.project_root / ".intent"
        self.graph_path = self.intent_dir / "graph.json"
        self.config_path = self.intent_dir / "config.json"

    def initialize(self, project_name: str) -> IntentGraph:
        if self.graph_path.exists():
            raise FileExistsError(f"Intent Kit is already initialized in {self.project_root}")
        self.intent_dir.mkdir(parents=True, exist_ok=True)
        graph = IntentGraph(project_name=project_name.strip() or self.project_root.name)
        self.save(graph)
        self.config_path.write_text(
            json.dumps({"renderer": "markdown", "schema_version": GRAPH_SCHEMA_VERSION}, indent=2) + "\n",
            encoding="utf-8",
        )
        return graph

    def load(self) -> IntentGraph:
        if not self.graph_path.exists():
            raise FileNotFoundError(
                f"No Intent Kit project found at {self.project_root}. Run 'intentkit init' first."
            )
        return IntentGraph.from_dict(json.loads(self.graph_path.read_text(encoding="utf-8")))

    def save(self, graph: IntentGraph) -> None:
        errors = graph.validate()
        if errors:
            raise ValueError("Cannot save invalid graph: " + "; ".join(errors))
        self.intent_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.graph_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_path.replace(self.graph_path)
