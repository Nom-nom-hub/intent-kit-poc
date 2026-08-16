import json
from pathlib import Path

import pytest

from intentkit.policies import PolicyRegistry, policy_pack_from_mapping


def test_shipped_policies_have_deterministic_defaults(tmp_path: Path) -> None:
    registry = PolicyRegistry.from_project(tmp_path)

    assert [pack.name for pack in registry.list()] == [
        "documentation",
        "migration",
        "release-critical",
    ]
    release = registry.resolve("release-critical")
    assert release.risk == "R3"
    assert release.evaluation == "all"
    assert release.proof_required is True
    assert release.review_required is True
    assert "release-critical policy pack" in release.proof_description("Ship safely")


def test_project_policy_pack_is_loaded_without_overriding_builtin(tmp_path: Path) -> None:
    policy_dir = tmp_path / ".intent"
    policy_dir.mkdir()
    (policy_dir / "policies.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "packs": [
                    {
                        "name": "team-review",
                        "title": "Team Review",
                        "description": "Require team review for important changes.",
                        "risk": "R2",
                        "evaluation": "manual",
                        "proof_required": True,
                        "evidence_freshness_days": 14,
                        "review_required": True,
                        "source_provenance_required": False,
                        "required_checkers": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    pack = PolicyRegistry.from_project(tmp_path).resolve("team-review")

    assert pack.risk == "R2"
    assert pack.evidence_freshness_days == 14
    assert pack.to_properties()["review_required"] is True


def test_builtin_override_and_invalid_policy_shape_are_rejected(tmp_path: Path) -> None:
    policy_dir = tmp_path / ".intent"
    policy_dir.mkdir()
    (policy_dir / "policies.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "packs": [
                    {
                        "name": "release-critical",
                        "title": "Override",
                        "description": "Should not be allowed.",
                        "risk": "R3",
                        "evaluation": "all",
                        "proof_required": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="cannot override"):
        PolicyRegistry.from_project(tmp_path)
    with pytest.raises(ValueError, match="unsupported risk"):
        policy_pack_from_mapping(
            {
                "name": "invalid-risk",
                "title": "Invalid",
                "description": "Invalid policy pack.",
                "risk": "R9",
                "evaluation": "manual",
                "proof_required": True,
            }
        )


def test_policy_template_is_written_once(tmp_path: Path) -> None:
    registry = PolicyRegistry.from_project(tmp_path)

    path = registry.write_template()

    assert path == tmp_path / ".intent" / "policies.json"
    assert '"team-review"' in path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        registry.write_template()
