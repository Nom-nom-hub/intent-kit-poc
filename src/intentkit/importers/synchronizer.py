"""Reviewed, deterministic synchronization for previously imported Spec Kit features.

The synchronizer never writes to the Spec Kit source directory. It derives a current
source-managed record set, compares that set with the canonical graph, writes a
review proposal, and applies the proposal only after an explicit caller decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..insights import analyze_impact
from ..kernel import GraphStore, IntentGraph, Node, NodeStatus, NodeType, RelationType, utc_now
from ..renderer import MarkdownRenderer
from .speckit import (
    IMPORTER_ID,
    Artifact,
    SpecKitImporter,
    extract_section,
    parse_feature_description,
    parse_feature_name,
    parse_functional_requirements,
    parse_success_criteria,
    parse_tasks,
    parse_user_stories,
    section_line,
    short_title,
)

SYNC_SCHEMA_VERSION = 1
PROPOSAL_DIRECTORY = "sync-proposals"


@dataclass(frozen=True, slots=True)
class ManagedRecord:
    """One source-managed graph record with a stable source key."""

    key: str
    node_type: str
    title: str
    description: str
    status: str
    properties: dict[str, Any]
    source_managed_status: bool = False


@dataclass(frozen=True, slots=True)
class ManagedLink:
    """A source-managed typed relation expressed with stable record keys."""

    source_key: str
    target_key: str
    relation: str


@dataclass(frozen=True, slots=True)
class SyncDelta:
    """A reviewable node delta between source and graph."""

    action: str
    key: str
    node_id: str | None
    node_type: str
    title: str
    changes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SyncProposal:
    """A fully deterministic synchronization plan with approval prerequisites."""

    proposal_id: str
    source_root: str
    base_graph_digest: str
    source_digests: dict[str, str]
    deltas: tuple[SyncDelta, ...]
    links_to_add: tuple[ManagedLink, ...]
    links_to_remove: tuple[ManagedLink, ...]
    impacted_node_ids: tuple[str, ...]
    proof_gap_ids: tuple[str, ...]

    @property
    def change_count(self) -> int:
        return sum(delta.action != "unchanged" for delta in self.deltas)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SYNC_SCHEMA_VERSION,
            "proposal_id": self.proposal_id,
            "source_root": self.source_root,
            "base_graph_digest": self.base_graph_digest,
            "source_digests": dict(sorted(self.source_digests.items())),
            "deltas": [asdict(delta) | {"changes": list(delta.changes)} for delta in self.deltas],
            "links_to_add": [asdict(link) for link in self.links_to_add],
            "links_to_remove": [asdict(link) for link in self.links_to_remove],
            "impacted_node_ids": list(self.impacted_node_ids),
            "proof_gap_ids": list(self.proof_gap_ids),
            "approval": {
                "required": True,
                "apply_command": "intentkit sync-speckit SOURCE --proposal PROPOSAL.json --apply",
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SyncProposal:
        if payload.get("schema_version") != SYNC_SCHEMA_VERSION:
            raise ValueError("Unsupported synchronization proposal schema version.")
        return cls(
            proposal_id=required_text(payload, "proposal_id"),
            source_root=required_text(payload, "source_root"),
            base_graph_digest=required_text(payload, "base_graph_digest"),
            source_digests=string_mapping(payload.get("source_digests"), "source_digests"),
            deltas=tuple(
                SyncDelta(
                    action=required_text(item, "action"),
                    key=required_text(item, "key"),
                    node_id=optional_text(item.get("node_id")),
                    node_type=required_text(item, "node_type"),
                    title=required_text(item, "title"),
                    changes=tuple(string_list(item.get("changes"), "changes")),
                )
                for item in object_list(payload.get("deltas"), "deltas")
            ),
            links_to_add=tuple(
                managed_link_from_dict(item)
                for item in object_list(payload.get("links_to_add"), "links_to_add")
            ),
            links_to_remove=tuple(
                managed_link_from_dict(item)
                for item in object_list(payload.get("links_to_remove"), "links_to_remove")
            ),
            impacted_node_ids=tuple(
                string_list(payload.get("impacted_node_ids"), "impacted_node_ids")
            ),
            proof_gap_ids=tuple(string_list(payload.get("proof_gap_ids"), "proof_gap_ids")),
        )


@dataclass(frozen=True, slots=True)
class SyncApplyReport:
    """Summary of an applied, source-verified proposal."""

    proposal_id: str
    added: int
    updated: int
    removed: int
    links_added: int
    links_removed: int
    record_path: Path


class SpecKitSynchronizer:
    """Generate and apply reviewed changes for one previously imported feature."""

    def __init__(self, source_root: Path):
        self.source_root = source_root.expanduser().resolve()
        self.importer = SpecKitImporter(self.source_root)

    def propose(self, graph: IntentGraph) -> SyncProposal:
        """Compare current source records with the existing imported graph without mutation."""

        self.importer = SpecKitImporter(self.source_root)
        records, links = self._managed_model()
        existing = self._existing_by_key(graph)
        if not existing:
            raise ValueError(
                f"Spec Kit source {self.source_root} is not imported into this graph. "
                "Use import-speckit before synchronization."
            )
        deltas: list[SyncDelta] = []
        for key, record in sorted(records.items()):
            node = existing.get(key)
            if node is None:
                deltas.append(
                    SyncDelta("added", key, None, record.node_type, record.title, ("new",))
                )
                continue
            changes = tuple(self._record_changes(node, record))
            action = "unchanged" if not changes else "updated"
            deltas.append(SyncDelta(action, key, node.id, record.node_type, record.title, changes))
        for key, node in sorted(existing.items()):
            if key not in records:
                deltas.append(
                    SyncDelta(
                        "removed",
                        key,
                        node.id,
                        node.type,
                        node.title,
                        ("missing_from_source",),
                    )
                )

        current_links = self._existing_managed_links(graph, existing)
        desired_links = set(links)
        links_to_add = tuple(sorted(desired_links - current_links, key=link_sort_key))
        links_to_remove = tuple(sorted(current_links - desired_links, key=link_sort_key))
        impacted, gaps = self._impact(graph, deltas)
        source_digests = self._source_digests()
        proposal_material = {
            "schema_version": SYNC_SCHEMA_VERSION,
            "source_root": str(self.source_root),
            "base_graph_digest": graph_digest(graph),
            "source_digests": source_digests,
            "deltas": [asdict(delta) for delta in deltas],
            "links_to_add": [asdict(link) for link in links_to_add],
            "links_to_remove": [asdict(link) for link in links_to_remove],
        }
        proposal_id = "sync-" + digest_payload(proposal_material)[:16]
        return SyncProposal(
            proposal_id=proposal_id,
            source_root=str(self.source_root),
            base_graph_digest=proposal_material["base_graph_digest"],
            source_digests=source_digests,
            deltas=tuple(deltas),
            links_to_add=links_to_add,
            links_to_remove=links_to_remove,
            impacted_node_ids=tuple(sorted(impacted)),
            proof_gap_ids=tuple(sorted(gaps)),
        )

    def write_proposal(self, store: GraphStore, proposal: SyncProposal) -> Path:
        """Persist a review artifact; writing a proposal never changes graph state."""

        directory = store.intent_dir / PROPOSAL_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{proposal.proposal_id}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != proposal.to_dict():
                raise FileExistsError(f"Existing proposal path has different content: {path}")
            return path
        path.write_text(
            json.dumps(proposal.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def apply(self, store: GraphStore, proposal: SyncProposal) -> SyncApplyReport:
        """Apply one revalidated proposal while preserving matching imported node IDs."""

        graph = store.load()
        fresh = self.propose(graph)
        if proposal != fresh:
            raise ValueError(
                "Synchronization proposal is stale. Regenerate and review a new proposal "
                "before apply."
            )
        records, links = self._managed_model()
        existing = self._existing_by_key(graph)
        key_to_id: dict[str, str] = {key: node.id for key, node in existing.items()}
        added = updated = removed = 0
        for delta in proposal.deltas:
            if delta.action == "added":
                record = records[delta.key]
                node = graph.add_node(
                    record.node_type,
                    record.title,
                    record.description,
                    status=record.status,
                    properties=record.properties,
                )
                key_to_id[delta.key] = node.id
                added += 1
            elif delta.action == "updated":
                record = records[delta.key]
                current = graph.get_node(delta.node_id or "")
                properties = merge_import_properties(current.properties, record.properties)
                status = record.status if record.source_managed_status else current.status
                graph.update_node(
                    current.id,
                    title=record.title,
                    description=record.description,
                    status=status,
                    properties=properties,
                )
                updated += 1
            elif delta.action == "removed":
                graph.remove_node(delta.node_id or "")
                key_to_id.pop(delta.key, None)
                removed += 1

        existing_after = self._existing_by_key(graph)
        links_removed = reconcile_removed_links(graph, proposal.links_to_remove, existing_after)
        links_added = reconcile_added_links(graph, links, existing_after)
        errors = graph.validate()
        if errors:
            raise ValueError("Synchronization would create an invalid graph: " + "; ".join(errors))
        store.save(graph)
        MarkdownRenderer(store.project_root).render(graph)
        record_path = self._write_apply_record(
            store,
            proposal,
            added,
            updated,
            removed,
            links_added,
            links_removed,
        )
        return SyncApplyReport(
            proposal_id=proposal.proposal_id,
            added=added,
            updated=updated,
            removed=removed,
            links_added=links_added,
            links_removed=links_removed,
            record_path=record_path,
        )

    def _managed_model(self) -> tuple[dict[str, ManagedRecord], tuple[ManagedLink, ...]]:
        feature_name = parse_feature_name(self.importer.spec)
        records: dict[str, ManagedRecord] = {}
        outcome_key = "feature"
        records[outcome_key] = ManagedRecord(
            outcome_key,
            NodeType.OUTCOME.value,
            f"Imported Spec Kit feature: {feature_name}",
            parse_feature_description(self.importer.spec)
            or f"Imported from {self.importer.spec.relative_path}.",
            NodeStatus.ACTIVE.value,
            {
                **self._provenance(self.importer.spec, 1),
                "source_kind": "speckit_feature",
                "success_measures": [
                    criterion.description
                    for criterion in parse_success_criteria(self.importer.spec)
                ],
            },
        )
        links: list[ManagedLink] = []
        for story in parse_user_stories(self.importer.spec):
            key = f"story:US{story.number}"
            records[key] = ManagedRecord(
                key,
                NodeType.REQUIREMENT.value,
                f"{story.priority} user story: {story.title}",
                story.description or story.title,
                NodeStatus.ACTIVE.value,
                {
                    **self._provenance(self.importer.spec, story.line),
                    "source_kind": "speckit_user_story",
                    "story_label": f"US{story.number}",
                    "priority": story.priority,
                    "independent_test": story.independent_test,
                    "acceptance_scenarios": list(story.acceptance_scenarios),
                },
            )
            links.append(ManagedLink(key, outcome_key, RelationType.DERIVES_FROM.value))
        for requirement in parse_functional_requirements(self.importer.spec):
            key = f"functional:{requirement.identifier}"
            records[key] = ManagedRecord(
                key,
                NodeType.REQUIREMENT.value,
                f"{requirement.identifier}: {short_title(requirement.description)}",
                requirement.description,
                NodeStatus.ACTIVE.value,
                {
                    **self._provenance(self.importer.spec, requirement.line),
                    "source_kind": "speckit_functional_requirement",
                    "source_identifier": requirement.identifier,
                },
            )
            links.append(ManagedLink(key, outcome_key, RelationType.DERIVES_FROM.value))
        if self.importer.plan:
            summary = extract_section(self.importer.plan, "Summary")
            technical_context = extract_section(self.importer.plan, "Technical Context")
            description = join_nonempty([summary, technical_context])
            if description:
                key = "plan"
                records[key] = ManagedRecord(
                    key,
                    NodeType.DECISION.value,
                    f"Imported implementation plan: {feature_name}",
                    description,
                    NodeStatus.PROPOSED.value,
                    {
                        **self._provenance(
                            self.importer.plan, section_line(self.importer.plan, "Summary") or 1
                        ),
                        "source_kind": "speckit_plan",
                    },
                )
        if self.importer.tasks:
            for task in parse_tasks(self.importer.tasks):
                key = f"task:{task.identifier}"
                records[key] = ManagedRecord(
                    key,
                    NodeType.IMPLEMENTATION_TASK.value,
                    f"{task.identifier}: {short_title(task.description)}",
                    task.description,
                    NodeStatus.VERIFIED.value if task.complete else NodeStatus.PLANNED.value,
                    {
                        **self._provenance(self.importer.tasks, task.line),
                        "source_kind": "speckit_task",
                        "source_identifier": task.identifier,
                        "phase": task.phase,
                        "parallel": task.parallel,
                        "story_label": task.story_label,
                        "complete": task.complete,
                    },
                    source_managed_status=True,
                )
                if task.story_label:
                    links.append(
                        ManagedLink(key, f"story:{task.story_label}", RelationType.IMPLEMENTS.value)
                    )
        return records, tuple(links)

    def _existing_by_key(self, graph: IntentGraph) -> dict[str, Node]:
        records: dict[str, Node] = {}
        for node in graph.nodes.values():
            provenance = node.properties.get("provenance")
            if not isinstance(provenance, dict):
                continue
            if provenance.get("importer") != IMPORTER_ID:
                continue
            if provenance.get("source_root") != str(self.source_root):
                continue
            key = key_for_node(node)
            if key:
                if key in records:
                    raise ValueError(f"Duplicate imported source key in graph: {key}")
                records[key] = node
        return records

    def _existing_managed_links(
        self, graph: IntentGraph, existing: dict[str, Node]
    ) -> set[ManagedLink]:
        ids_to_keys = {node.id: key for key, node in existing.items()}
        links: set[ManagedLink] = set()
        for edge in graph.edges.values():
            source_key = ids_to_keys.get(edge.source)
            target_key = ids_to_keys.get(edge.target)
            if source_key and target_key:
                links.add(ManagedLink(source_key, target_key, edge.relation))
        return links

    def _record_changes(self, node: Node, record: ManagedRecord) -> list[str]:
        changes: list[str] = []
        if node.type != record.node_type:
            changes.append("type")
        if node.title != record.title:
            changes.append("title")
        if node.description != record.description:
            changes.append("description")
        for key, value in record.properties.items():
            if node.properties.get(key) != value:
                changes.append(f"properties.{key}")
        if record.source_managed_status and node.status != record.status:
            changes.append("status")
        return changes

    def _impact(self, graph: IntentGraph, deltas: list[SyncDelta]) -> tuple[set[str], set[str]]:
        impacted: set[str] = set()
        proof_gaps: set[str] = set()
        for delta in deltas:
            if delta.action == "unchanged" or not delta.node_id:
                continue
            report = analyze_impact(graph, delta.node_id)
            impacted.add(delta.node_id)
            impacted.update(path.node.id for path in report.paths)
            proof_gaps.update(node.id for node in report.proof_gaps)
        return impacted, proof_gaps

    def _source_digests(self) -> dict[str, str]:
        artifacts = [self.importer.spec, self.importer.plan, self.importer.tasks]
        return {
            artifact.relative_path: f"sha256:{artifact.digest}"
            for artifact in artifacts
            if artifact is not None
        }

    def _provenance(self, artifact: Artifact, line: int) -> dict[str, Any]:
        return {
            "provenance": {
                "importer": IMPORTER_ID,
                "source_root": str(self.source_root),
                "artifact": artifact.relative_path,
                "sha256": f"sha256:{artifact.digest}",
                "line": line,
            }
        }

    def _write_apply_record(
        self,
        store: GraphStore,
        proposal: SyncProposal,
        added: int,
        updated: int,
        removed: int,
        links_added: int,
        links_removed: int,
    ) -> Path:
        directory = store.intent_dir / PROPOSAL_DIRECTORY
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{proposal.proposal_id}.applied.json"
        payload = {
            "proposal_id": proposal.proposal_id,
            "applied_at": utc_now(),
            "source_root": proposal.source_root,
            "added": added,
            "updated": updated,
            "removed": removed,
            "links_added": links_added,
            "links_removed": links_removed,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path


def graph_digest(graph: IntentGraph) -> str:
    return "sha256:" + digest_payload(graph.to_dict())


def digest_payload(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def key_for_node(node: Node) -> str | None:
    source_kind = node.properties.get("source_kind")
    if source_kind == "speckit_feature":
        return "feature"
    if source_kind == "speckit_user_story":
        label = node.properties.get("story_label")
        return f"story:{label}" if isinstance(label, str) else None
    if source_kind == "speckit_functional_requirement":
        identifier = node.properties.get("source_identifier")
        return f"functional:{identifier}" if isinstance(identifier, str) else None
    if source_kind == "speckit_plan":
        return "plan"
    if source_kind == "speckit_task":
        identifier = node.properties.get("source_identifier")
        return f"task:{identifier}" if isinstance(identifier, str) else None
    return None


def merge_import_properties(existing: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    """Preserve non-importer metadata while refreshing only source-managed fields."""

    merged = dict(existing)
    merged.update(desired)
    return merged


def reconcile_removed_links(
    graph: IntentGraph, removed: tuple[ManagedLink, ...], existing: dict[str, Node]
) -> int:
    ids = {key: node.id for key, node in existing.items()}
    removed_count = 0
    for link in removed:
        source_id = ids.get(link.source_key)
        target_id = ids.get(link.target_key)
        if not source_id or not target_id:
            continue
        for edge_id in [
            edge.id
            for edge in graph.edges.values()
            if edge.source == source_id
            and edge.target == target_id
            and edge.relation == link.relation
        ]:
            del graph.edges[edge_id]
            graph.touch()
            removed_count += 1
    return removed_count


def reconcile_added_links(
    graph: IntentGraph, links: tuple[ManagedLink, ...], existing: dict[str, Node]
) -> int:
    ids = {key: node.id for key, node in existing.items()}
    added = 0
    for link in links:
        source = ids.get(link.source_key)
        target = ids.get(link.target_key)
        if not source or not target:
            continue
        if any(
            edge.source == source and edge.target == target and edge.relation == link.relation
            for edge in graph.edges.values()
        ):
            continue
        graph.add_edge(source, target, link.relation)
        added += 1
    return added


def link_sort_key(link: ManagedLink) -> tuple[str, str, str]:
    return link.source_key, link.target_key, link.relation


def managed_link_from_dict(payload: dict[str, Any]) -> ManagedLink:
    return ManagedLink(
        source_key=required_text(payload, "source_key"),
        target_key=required_text(payload, "target_key"),
        relation=required_text(payload, "relation"),
    )


def required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Synchronization proposal requires a non-empty {key}.")
    return value


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Synchronization proposal node_id must be a string or null.")
    return value


def string_mapping(value: object, label: str) -> dict[str, str]:
    valid_mapping = isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )
    if not valid_mapping:
        raise ValueError(f"Synchronization proposal {label} must be a string mapping.")
    return dict(value)


def string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Synchronization proposal {label} must be a string list.")
    return list(value)


def object_list(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Synchronization proposal {label} must be an object list.")
    return list(value)


def join_nonempty(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part)
