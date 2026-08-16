"""Read-only importer for completed Spec Kit feature artifacts.

The importer deliberately uses a small, documented subset of Spec Kit's rendered
Markdown conventions. It never changes the source feature directory. Imported
nodes carry source provenance so reviewers can trace each graph record to the
artifact, line, and content hash that produced it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..kernel import IntentGraph, Node, NodeStatus, NodeType, RelationType

IMPORTER_ID = "intentkit.speckit"
SPEC_FILE = "spec.md"
PLAN_FILE = "plan.md"
TASKS_FILE = "tasks.md"

FEATURE_HEADING = re.compile(r"^#\s+Feature Specification:\s*(?P<title>.+?)\s*$")
USER_STORY_HEADING = re.compile(
    r"^###\s+User Story\s+(?P<number>\d+)\s+-\s+"
    r"(?P<title>.+?)\s+\(Priority:\s*(?P<priority>P\d+)\)\s*$"
)
FUNCTIONAL_REQUIREMENT = re.compile(
    r"^-\s+\*\*(?P<identifier>FR-\d+)\*\*:\s*(?P<description>.+?)\s*$"
)
SUCCESS_CRITERION = re.compile(r"^-\s+\*\*(?P<identifier>SC-\d+)\*\*:\s*(?P<description>.+?)\s*$")
TASK = re.compile(r"^-\s+\[(?P<complete>[ xX])\]\s+(?P<identifier>T\d+)\s+(?P<body>.+?)\s*$")
STORY_LABEL = re.compile(r"\[(?P<label>US\d+)\]")
SECTION_HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True, slots=True)
class Artifact:
    """Immutable text and provenance for a source artifact."""

    path: Path
    relative_path: str
    content: str
    digest: str

    @property
    def lines(self) -> list[str]:
        return self.content.splitlines()


@dataclass(frozen=True, slots=True)
class UserStory:
    """A Spec Kit user story extracted from a feature specification."""

    number: int
    title: str
    priority: str
    description: str
    independent_test: str | None
    acceptance_scenarios: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class Requirement:
    """A functional requirement extracted from a feature specification."""

    identifier: str
    description: str
    line: int


@dataclass(frozen=True, slots=True)
class Task:
    """An implementation task extracted from a Spec Kit task list."""

    identifier: str
    description: str
    complete: bool
    parallel: bool
    story_label: str | None
    phase: str | None
    line: int


@dataclass(frozen=True, slots=True)
class ImportReport:
    """A compact summary of a completed graph import."""

    source_root: Path
    feature_outcome_id: str
    user_stories: int
    functional_requirements: int
    decisions: int
    tasks: int

    @property
    def total_nodes(self) -> int:
        return 1 + self.user_stories + self.functional_requirements + self.decisions + self.tasks


class SpecKitImporter:
    """Import one completed Spec Kit feature directory into an Intent Kit graph."""

    def __init__(self, source_root: Path):
        self.source_root = source_root.expanduser().resolve()
        self.spec = self._load_required(SPEC_FILE)
        self.plan = self._load_optional(PLAN_FILE)
        self.tasks = self._load_optional(TASKS_FILE)

    def import_into(self, graph: IntentGraph) -> ImportReport:
        """Create provenance-rich graph records without changing source artifacts."""

        self._ensure_not_imported(graph)
        feature_name = parse_feature_name(self.spec)
        feature_outcome = graph.add_node(
            NodeType.OUTCOME,
            f"Imported Spec Kit feature: {feature_name}",
            parse_feature_description(self.spec) or f"Imported from {self.spec.relative_path}.",
            status=NodeStatus.ACTIVE,
            properties={
                **self._provenance(self.spec, 1),
                "source_kind": "speckit_feature",
                "success_measures": [
                    criterion.description for criterion in parse_success_criteria(self.spec)
                ],
            },
        )

        stories = parse_user_stories(self.spec)
        story_requirements: dict[str, Node] = {}
        for story in stories:
            requirement = graph.add_node(
                NodeType.REQUIREMENT,
                f"{story.priority} user story: {story.title}",
                story.description or story.title,
                status=NodeStatus.ACTIVE,
                properties={
                    **self._provenance(self.spec, story.line),
                    "source_kind": "speckit_user_story",
                    "story_label": f"US{story.number}",
                    "priority": story.priority,
                    "independent_test": story.independent_test,
                    "acceptance_scenarios": list(story.acceptance_scenarios),
                },
            )
            graph.add_edge(requirement.id, feature_outcome.id, RelationType.DERIVES_FROM)
            story_requirements[f"US{story.number}"] = requirement

        functional_requirements = parse_functional_requirements(self.spec)
        for requirement in functional_requirements:
            imported_requirement = graph.add_node(
                NodeType.REQUIREMENT,
                f"{requirement.identifier}: {short_title(requirement.description)}",
                requirement.description,
                status=NodeStatus.ACTIVE,
                properties={
                    **self._provenance(self.spec, requirement.line),
                    "source_kind": "speckit_functional_requirement",
                    "source_identifier": requirement.identifier,
                },
            )
            graph.add_edge(imported_requirement.id, feature_outcome.id, RelationType.DERIVES_FROM)

        decisions = 0
        if self.plan:
            summary = extract_section(self.plan, "Summary")
            technical_context = extract_section(self.plan, "Technical Context")
            description = join_nonempty([summary, technical_context])
            if description:
                graph.add_node(
                    NodeType.DECISION,
                    f"Imported implementation plan: {feature_name}",
                    description,
                    status=NodeStatus.PROPOSED,
                    properties={
                        **self._provenance(self.plan, section_line(self.plan, "Summary") or 1),
                        "source_kind": "speckit_plan",
                    },
                )
                decisions = 1

        tasks = parse_tasks(self.tasks) if self.tasks else []
        for task in tasks:
            task_node = graph.add_node(
                NodeType.IMPLEMENTATION_TASK,
                f"{task.identifier}: {short_title(task.description)}",
                task.description,
                status=NodeStatus.VERIFIED if task.complete else NodeStatus.PLANNED,
                properties={
                    **self._provenance(self.tasks, task.line),
                    "source_kind": "speckit_task",
                    "source_identifier": task.identifier,
                    "phase": task.phase,
                    "parallel": task.parallel,
                    "story_label": task.story_label,
                    "complete": task.complete,
                },
            )
            if task.story_label and task.story_label in story_requirements:
                graph.add_edge(
                    task_node.id,
                    story_requirements[task.story_label].id,
                    RelationType.IMPLEMENTS,
                )

        return ImportReport(
            source_root=self.source_root,
            feature_outcome_id=feature_outcome.id,
            user_stories=len(stories),
            functional_requirements=len(functional_requirements),
            decisions=decisions,
            tasks=len(tasks),
        )

    def _load_required(self, filename: str) -> Artifact:
        artifact = self._load_optional(filename)
        if not artifact:
            raise FileNotFoundError(f"Spec Kit import requires {filename} in {self.source_root}.")
        return artifact

    def _load_optional(self, filename: str) -> Artifact | None:
        path = self.source_root / filename
        if not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        return Artifact(
            path=path,
            relative_path=filename,
            content=content,
            digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _ensure_not_imported(self, graph: IntentGraph) -> None:
        root = str(self.source_root)
        for node in graph.nodes.values():
            provenance = node.properties.get("provenance")
            if isinstance(provenance, dict) and provenance.get("source_root") == root:
                raise ValueError(
                    f"Spec Kit source {self.source_root} has already been imported "
                    "into this graph. "
                    "Create a new Intent Kit project before importing it again."
                )

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


def parse_feature_name(spec: Artifact) -> str:
    for line in spec.lines:
        if match := FEATURE_HEADING.match(line):
            return match.group("title").strip("[] ") or spec.path.parent.name
    return spec.path.parent.name


def parse_feature_description(spec: Artifact) -> str:
    for line in spec.lines:
        if line.startswith("**Input**:"):
            return line.removeprefix("**Input**:").strip().strip('"')
    return ""


def parse_user_stories(spec: Artifact) -> list[UserStory]:
    stories: list[UserStory] = []
    lines = spec.lines
    current_match: re.Match[str] | None = None
    current_start = 0
    for index, line in enumerate(lines, start=1):
        if match := USER_STORY_HEADING.match(line):
            if current_match:
                stories.append(build_user_story(lines, current_match, current_start, index - 1))
            current_match = match
            current_start = index
        elif current_match and line.startswith("## "):
            stories.append(build_user_story(lines, current_match, current_start, index - 1))
            current_match = None
    if current_match:
        stories.append(build_user_story(lines, current_match, current_start, len(lines)))
    return stories


def build_user_story(
    lines: list[str], match: re.Match[str], start_line: int, end_line: int
) -> UserStory:
    block = lines[start_line:end_line]
    description_lines: list[str] = []
    for line in block:
        stripped = line.strip()
        if stripped.startswith("**Why this priority**:") or stripped.startswith(
            "**Independent Test**:"
        ):
            break
        if stripped and not stripped.startswith("<!--") and not stripped.startswith("---"):
            description_lines.append(stripped)
    acceptance_scenarios = extract_labeled_list(block, "**Acceptance Scenarios**:")
    return UserStory(
        number=int(match.group("number")),
        title=match.group("title").strip(),
        priority=match.group("priority"),
        description=" ".join(description_lines),
        independent_test=extract_labeled_value(block, "**Independent Test**:"),
        acceptance_scenarios=tuple(acceptance_scenarios),
        line=start_line,
    )


def parse_functional_requirements(spec: Artifact) -> list[Requirement]:
    return [
        Requirement(match.group("identifier"), match.group("description"), line)
        for line, text in enumerate(spec.lines, start=1)
        if (match := FUNCTIONAL_REQUIREMENT.match(text))
    ]


def parse_success_criteria(spec: Artifact) -> list[Requirement]:
    return [
        Requirement(match.group("identifier"), match.group("description"), line)
        for line, text in enumerate(spec.lines, start=1)
        if (match := SUCCESS_CRITERION.match(text))
    ]


def parse_tasks(tasks: Artifact) -> list[Task]:
    parsed: list[Task] = []
    phase: str | None = None
    for line_number, line in enumerate(tasks.lines, start=1):
        if heading := SECTION_HEADING.match(line):
            title = heading.group("title")
            phase = title if title.startswith("Phase ") else phase
        if match := TASK.match(line):
            body = match.group("body")
            story = STORY_LABEL.search(body)
            parsed.append(
                Task(
                    identifier=match.group("identifier"),
                    description=clean_task_description(body),
                    complete=match.group("complete").lower() == "x",
                    parallel="[P]" in body,
                    story_label=story.group("label") if story else None,
                    phase=phase,
                    line=line_number,
                )
            )
    return parsed


def extract_section(artifact: Artifact, heading: str) -> str:
    lines = artifact.lines
    start = section_line(artifact, heading)
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if stripped and not stripped.startswith("<!--") and not stripped.endswith("-->"):
            collected.append(stripped)
    return "\n".join(collected)


def section_line(artifact: Artifact, heading: str) -> int | None:
    needle = f"## {heading}".lower()
    for number, line in enumerate(artifact.lines, start=1):
        if line.strip().lower() == needle:
            return number
    return None


def extract_labeled_value(lines: list[str], label: str) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(label):
            value = stripped.removeprefix(label).strip()
            return value or None
    return None


def extract_labeled_list(lines: list[str], label: str) -> list[str]:
    values: list[str] = []
    collecting = False
    for line in lines:
        stripped = line.strip()
        if stripped == label:
            collecting = True
            continue
        if collecting and (stripped.startswith("**") or stripped.startswith("### ")):
            break
        if collecting and re.match(r"^\d+\.\s+", stripped):
            values.append(re.sub(r"^\d+\.\s+", "", stripped))
    return values


def clean_task_description(body: str) -> str:
    without_labels = STORY_LABEL.sub("", body).replace("[P]", "")
    return re.sub(r"\s+", " ", without_labels).strip()


def join_nonempty(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part)


def short_title(text: str, limit: int = 72) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1].rstrip()}…"
