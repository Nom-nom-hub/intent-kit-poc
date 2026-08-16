"""Deterministic graph insight queries for Intent Kit.

The module deliberately separates observation from mutation. Drift checks only read
recorded provenance and source artifacts; impact queries only traverse the stored
graph. Neither command changes the graph, source material, or rendered Markdown.
"""

from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .kernel import Edge, IntentGraph, Node, NodeStatus, NodeType


class DriftStatus(StrEnum):
    """Current source state compared with an imported provenance record."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    MISSING = "missing"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class DriftRecord:
    """One imported artifact and the graph nodes derived from it."""

    source_root: str
    artifact: str
    expected_digest: str
    current_digest: str | None
    status: DriftStatus
    node_ids: tuple[str, ...]

    @property
    def source_path(self) -> Path:
        return Path(self.source_root) / self.artifact


@dataclass(frozen=True, slots=True)
class ImpactHop:
    """A path edge from the queried graph node to an affected node."""

    edge_id: str
    relation: str
    direction: str
    node_id: str


@dataclass(frozen=True, slots=True)
class ImpactPath:
    """One deterministic shortest path from a query node to a connected node."""

    node: Node
    hops: tuple[ImpactHop, ...]

    @property
    def depth(self) -> int:
        return len(self.hops)


@dataclass(frozen=True, slots=True)
class ImpactReport:
    """Connected graph paths and revalidation gaps for a query node."""

    root: Node
    paths: tuple[ImpactPath, ...]
    proof_gaps: tuple[Node, ...]


def scan_drift(graph: IntentGraph, source: Path | None = None) -> list[DriftRecord]:
    """Compare imported artifact hashes with their current on-disk source files.

    When a source filter is provided, it may identify an imported feature directory
    or a single source artifact. Nodes without an importer provenance object are
    intentionally excluded.
    """

    grouped: dict[tuple[str, str, str], list[str]] = {}
    for node in graph.nodes.values():
        provenance = node.properties.get("provenance")
        if not isinstance(provenance, dict):
            continue
        source_root = provenance.get("source_root")
        artifact = provenance.get("artifact")
        expected_digest = provenance.get("sha256")
        values = (source_root, artifact, expected_digest)
        if not all(isinstance(value, str) and value for value in values):
            continue
        if not matches_source_filter(source_root, artifact, source):
            continue
        grouped.setdefault((source_root, artifact, expected_digest), []).append(node.id)

    records: list[DriftRecord] = []
    for (source_root, artifact, expected_digest), node_ids in sorted(grouped.items()):
        source_path, safe = resolve_artifact_path(source_root, artifact)
        if not safe:
            status = DriftStatus.UNSUPPORTED
            current_digest = None
        elif not source_path.is_file():
            status = DriftStatus.MISSING
            current_digest = None
        else:
            current_digest = sha256_digest(source_path)
            status = (
                DriftStatus.UNCHANGED if current_digest == expected_digest else DriftStatus.CHANGED
            )
        records.append(
            DriftRecord(
                source_root=source_root,
                artifact=artifact,
                expected_digest=expected_digest,
                current_digest=current_digest,
                status=status,
                node_ids=tuple(sorted(node_ids)),
            )
        )
    return records


def analyze_impact(graph: IntentGraph, node_id: str) -> ImpactReport:
    """Return stable shortest paths to every connected graph node.

    Impact traversal deliberately follows both incoming and outgoing typed edges.
    A requirement can affect its originating outcome, its implementation tasks, and
    its proof obligations; treating only one edge direction as "impact" would hide
    useful revalidation context.
    """

    root = graph.get_node(node_id)
    paths: dict[str, tuple[ImpactHop, ...]] = {root.id: ()}
    queue: deque[str] = deque([root.id])

    while queue:
        current_id = queue.popleft()
        for edge, adjacent_id, direction in connected_edges(graph, current_id):
            if adjacent_id in paths:
                continue
            hop = ImpactHop(
                edge_id=edge.id,
                relation=edge.relation,
                direction=direction,
                node_id=adjacent_id,
            )
            paths[adjacent_id] = (*paths[current_id], hop)
            queue.append(adjacent_id)

    impacted_paths = tuple(
        ImpactPath(graph.get_node(impacted_id), hops)
        for impacted_id, hops in sorted(paths.items(), key=lambda item: (len(item[1]), item[0]))
        if impacted_id != root.id
    )
    proof_gaps = tuple(
        path.node
        for path in impacted_paths
        if path.node.type == NodeType.PROOF_OBLIGATION.value
        and path.node.status != NodeStatus.VERIFIED.value
    )
    return ImpactReport(root=root, paths=impacted_paths, proof_gaps=proof_gaps)


def source_nodes(graph: IntentGraph, source: Path) -> list[Node]:
    """Find graph nodes created from a source directory or a specific artifact."""

    matched: list[Node] = []
    for node in graph.nodes.values():
        provenance = node.properties.get("provenance")
        if not isinstance(provenance, dict):
            continue
        source_root = provenance.get("source_root")
        artifact = provenance.get("artifact")
        if not isinstance(source_root, str) or not isinstance(artifact, str):
            continue
        if matches_source_filter(source_root, artifact, source):
            matched.append(node)
    return sorted(matched, key=lambda item: item.id)


def render_drift(records: list[DriftRecord]) -> str:
    """Format a stable text summary for the CLI and automated tests."""

    counts = {status: 0 for status in DriftStatus}
    for record in records:
        counts[record.status] += 1
    lines = [
        "Drift scan: "
        f"{len(records)} tracked artifact(s) | "
        f"{counts[DriftStatus.UNCHANGED]} unchanged | "
        f"{counts[DriftStatus.CHANGED]} changed | "
        f"{counts[DriftStatus.MISSING]} missing | "
        f"{counts[DriftStatus.UNSUPPORTED]} unsupported",
    ]
    if not records:
        lines.append("No imported source provenance matched the requested scope.")
    for record in records:
        lines.append(
            f"{record.status.value.upper()}: {record.source_path} → {', '.join(record.node_ids)}"
        )
    return "\n".join(lines)


def render_impact(report: ImpactReport) -> str:
    """Format a stable text summary for an impact query."""

    lines = [
        f"Impact root: {report.root.id} — {report.root.title}",
        f"Connected nodes: {len(report.paths)} | Proof gaps: {len(report.proof_gaps)}",
    ]
    for path in report.paths:
        route = " → ".join(f"{hop.relation}:{hop.direction}:{hop.node_id}" for hop in path.hops)
        lines.append(
            f"DEPTH {path.depth}: {path.node.id} [{path.node.type}/{path.node.status}] via {route}"
        )
    if report.proof_gaps:
        lines.append("Proof gaps: " + ", ".join(node.id for node in report.proof_gaps))
    return "\n".join(lines)


def connected_edges(graph: IntentGraph, node_id: str) -> list[tuple[Edge, str, str]]:
    """Return adjacent edges in stable order, recording their traversal direction."""

    connected: list[tuple[Edge, str, str]] = []
    for edge in graph.edges.values():
        if edge.source == node_id:
            connected.append((edge, edge.target, "outgoing"))
        elif edge.target == node_id:
            connected.append((edge, edge.source, "incoming"))
    return sorted(
        connected,
        key=lambda item: (item[2], item[0].relation, item[1], item[0].id),
    )


def matches_source_filter(source_root: str, artifact: str, source: Path | None) -> bool:
    """Match an optional user path against a recorded root or source artifact."""

    if source is None:
        return True
    requested = source.expanduser().resolve()
    root = Path(source_root).expanduser().resolve()
    artifact_path, safe = resolve_artifact_path(source_root, artifact)
    return requested == root or (safe and requested == artifact_path)


def resolve_artifact_path(source_root: str, artifact: str) -> tuple[Path, bool]:
    """Resolve an artifact only when it remains inside its recorded source root."""

    root = Path(source_root).expanduser().resolve()
    candidate = (root / artifact).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate, False
    return candidate, True


def sha256_digest(path: Path) -> str:
    """Return the exact provenance digest format used by the Spec Kit importer."""

    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
