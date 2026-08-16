"""Local, version-controlled risk defaults for Intent Kit shaping workflows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .kernel import GraphStore

POLICY_SCHEMA_VERSION = "1"
PACK_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
VALID_RISKS = frozenset({"R0", "R1", "R2", "R3"})
VALID_EVALUATIONS = frozenset({"latest", "all", "any", "manual"})


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """A non-executable set of proof and review defaults for a requirement."""

    name: str
    title: str
    description: str
    risk: str
    evaluation: str
    proof_required: bool
    required_checkers: tuple[str, ...] = ()
    evidence_freshness_days: int | None = None
    review_required: bool = False
    source_provenance_required: bool = False

    def proof_title(self, requirement_title: str) -> str:
        return f"Verify {requirement_title}"

    def proof_description(self, requirement_title: str) -> str:
        clauses = [
            f"Provide evidence that '{requirement_title}' satisfies the {self.name} policy pack."
        ]
        if self.review_required:
            clauses.append("Record explicit review or automated validation evidence.")
        if self.source_provenance_required:
            clauses.append("Preserve source provenance or a reviewed migration record.")
        if self.evidence_freshness_days is not None:
            clauses.append(
                f"Evidence should be refreshed within {self.evidence_freshness_days} day(s) "
                "when the work changes."
            )
        return " ".join(clauses)

    def to_properties(self) -> dict[str, Any]:
        """Return JSON-safe policy metadata stored on shaped graph nodes."""

        return {
            "name": self.name,
            "title": self.title,
            "risk": self.risk,
            "evaluation": self.evaluation,
            "required_checkers": list(self.required_checkers),
            "proof_required": self.proof_required,
            "evidence_freshness_days": self.evidence_freshness_days,
            "review_required": self.review_required,
            "source_provenance_required": self.source_provenance_required,
        }


BUILTIN_POLICY_PACKS: tuple[PolicyPack, ...] = (
    PolicyPack(
        name="release-critical",
        title="Release Critical",
        description="High-risk work that needs explicit evidence and review before release.",
        risk="R3",
        evaluation="all",
        proof_required=True,
        evidence_freshness_days=7,
        review_required=True,
    ),
    PolicyPack(
        name="migration",
        title="Migration",
        description=(
            "Imported or transformed work that must retain provenance and reviewed evidence."
        ),
        risk="R2",
        evaluation="manual",
        proof_required=True,
        evidence_freshness_days=30,
        review_required=True,
        source_provenance_required=True,
    ),
    PolicyPack(
        name="documentation",
        title="Documentation",
        description=(
            "Low-risk user-facing documentation that needs a focused, current review record."
        ),
        risk="R1",
        evaluation="latest",
        proof_required=True,
        evidence_freshness_days=90,
    ),
)


class PolicyRegistry:
    """Resolve shipped and project-local policy packs without loading executable code."""

    def __init__(self, packs: dict[str, PolicyPack], source_path: Path | None = None):
        self._packs = dict(packs)
        self.source_path = source_path

    @classmethod
    def from_project(cls, project_root: Path) -> PolicyRegistry:
        builtins = {pack.name: pack for pack in BUILTIN_POLICY_PACKS}
        config_path = GraphStore(project_root).intent_dir / "policies.json"
        if not config_path.exists():
            return cls(builtins, config_path)
        payload = read_policy_config(config_path)
        for pack_payload in payload["packs"]:
            pack = policy_pack_from_mapping(pack_payload)
            if pack.name in builtins:
                raise ValueError(
                    f"Project policy '{pack.name}' cannot override a shipped policy pack. "
                    "Choose a distinct policy name."
                )
            builtins[pack.name] = pack
        return cls(builtins, config_path)

    def list(self) -> tuple[PolicyPack, ...]:
        return tuple(self._packs[name] for name in sorted(self._packs))

    def resolve(self, name: str) -> PolicyPack:
        try:
            return self._packs[name]
        except KeyError as exc:
            available = ", ".join(self._packs) or "none"
            message = f"Unknown policy pack '{name}'. Available packs: {available}."
            raise ValueError(message) from exc

    def write_template(self) -> Path:
        if self.source_path is None:
            raise ValueError("A project path is required to create policy configuration.")
        if self.source_path.exists():
            raise FileExistsError(f"Policy configuration already exists: {self.source_path}")
        self.source_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_path.write_text(
            json.dumps(
                {
                    "schema_version": POLICY_SCHEMA_VERSION,
                    "packs": [
                        {
                            "name": "team-review",
                            "title": "Team Review",
                            "description": (
                                "Example local policy pack. Rename or remove before use."
                            ),
                            "risk": "R2",
                            "evaluation": "manual",
                            "proof_required": True,
                            "evidence_freshness_days": 30,
                            "review_required": True,
                            "source_provenance_required": False,
                            "required_checkers": [],
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return self.source_path


def read_policy_config(path: Path) -> dict[str, Any]:
    """Load a strict, JSON-only project policy file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Policy configuration must be valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Policy configuration must be a JSON object.")
    if payload.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError(f"Policy configuration schema_version must be '{POLICY_SCHEMA_VERSION}'.")
    packs = payload.get("packs")
    if not isinstance(packs, list):
        raise ValueError("Policy configuration requires a 'packs' list.")
    if not all(isinstance(pack, dict) for pack in packs):
        raise ValueError("Each policy pack must be a JSON object.")
    names = [pack.get("name") for pack in packs]
    if len(names) != len(set(names)):
        raise ValueError("Policy configuration contains duplicate pack names.")
    return {"schema_version": POLICY_SCHEMA_VERSION, "packs": packs}


def policy_pack_from_mapping(payload: dict[str, Any]) -> PolicyPack:
    """Validate one JSON policy object and construct its immutable contract."""

    required_strings = ("name", "title", "description", "risk", "evaluation")
    for field_name in required_strings:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Policy pack field '{field_name}' must be a non-empty string.")
    name = payload["name"].strip()
    if not PACK_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Policy pack name must use lowercase letters, digits, and hyphens and be "
            "2-64 characters."
        )
    risk = payload["risk"]
    if risk not in VALID_RISKS:
        raise ValueError(f"Policy pack '{name}' uses unsupported risk '{risk}'.")
    evaluation = payload["evaluation"]
    if evaluation not in VALID_EVALUATIONS:
        raise ValueError(f"Policy pack '{name}' uses unsupported evaluation '{evaluation}'.")
    proof_required = payload.get("proof_required")
    if not isinstance(proof_required, bool):
        raise ValueError(f"Policy pack '{name}' requires a boolean proof_required field.")
    required_checkers = payload.get("required_checkers", [])
    if not isinstance(required_checkers, list) or not all(
        isinstance(checker, str) and checker.strip() for checker in required_checkers
    ):
        raise ValueError(
            f"Policy pack '{name}' required_checkers must be a list of non-empty strings."
        )
    freshness = payload.get("evidence_freshness_days")
    if freshness is not None and (not isinstance(freshness, int) or freshness < 1):
        raise ValueError(
            f"Policy pack '{name}' evidence_freshness_days must be a positive integer or null."
        )
    booleans = ("review_required", "source_provenance_required")
    for field_name in booleans:
        if not isinstance(payload.get(field_name, False), bool):
            raise ValueError(f"Policy pack '{name}' {field_name} must be a boolean.")
    return PolicyPack(
        name=name,
        title=payload["title"].strip(),
        description=payload["description"].strip(),
        risk=risk,
        evaluation=evaluation,
        proof_required=proof_required,
        required_checkers=tuple(required_checkers),
        evidence_freshness_days=freshness,
        review_required=payload.get("review_required", False),
        source_provenance_required=payload.get("source_provenance_required", False),
    )


def render_policy_list(registry: PolicyRegistry) -> str:
    """Format the available policy set for the CLI."""

    lines = ["Available policy packs:"]
    for pack in registry.list():
        proof = "required" if pack.proof_required else "optional"
        lines.append(
            f"- {pack.name}: {pack.title} [{pack.risk}, {pack.evaluation}, proof {proof}] "
            f"— {pack.description}"
        )
    if registry.source_path and registry.source_path.exists():
        lines.append(f"Project policy file: {registry.source_path}")
    return "\n".join(lines)


def render_policy_show(pack: PolicyPack) -> str:
    """Format detailed policy defaults for direct inspection."""

    lines = [
        f"Policy pack: {pack.name} — {pack.title}",
        pack.description,
        f"Risk: {pack.risk}",
        f"Proof required: {str(pack.proof_required).lower()}",
        f"Evaluation: {pack.evaluation}",
        "Required checkers: " + (", ".join(pack.required_checkers) or "none"),
        "Evidence freshness: "
        + (f"{pack.evidence_freshness_days} day(s)" if pack.evidence_freshness_days else "not set"),
        f"Review required: {str(pack.review_required).lower()}",
        f"Source provenance required: {str(pack.source_provenance_required).lower()}",
    ]
    return "\n".join(lines)
