from pathlib import Path

from intentkit.cli import main
from intentkit.kernel import GraphStore, NodeStatus


def test_cli_end_to_end_workflow(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    assert main(["init", "--path", root, "--project-name", "Checkout Safety"]) == 0
    assert (
        main(
            [
                "capture",
                "Prevent duplicate orders",
                "--path",
                root,
                "--description",
                "Retries must not create duplicate orders.",
                "--success-measure",
                "A repeated confirmation returns one order.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Use idempotency keys",
                "--path",
                root,
                "--description",
                "Every confirmation request must carry an idempotency key.",
                "--outcome",
                "OUT-001",
                "--risk",
                "R3",
                "--decision-title",
                "Use provider idempotency keys",
                "--rationale",
                "Provider-backed idempotency is safest.",
                "--alternative",
                "Time-window deduplication",
                "--proof-title",
                "Prove retries are safe",
                "--proof-description",
                "A repeated confirmation returns exactly one order.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "prove",
                "PRF-001",
                "Payment contract test",
                "--path",
                root,
                "--description",
                "The retry contract passed against the payment sandbox.",
                "--source",
                "tests/test_payment_contract.py",
                "--result",
                "pass",
            ]
        )
        == 0
    )
    assert main(["status", "--path", root]) == 0

    graph = GraphStore(tmp_path).load()
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    assert (tmp_path / "intent" / "intent.md").exists()
    assert "Payment contract test" in (tmp_path / "intent" / "evidence.md").read_text()
    assert "Proof coverage: 1/1 verified" in capsys.readouterr().out


def test_cli_runs_a_checker_backed_proof(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    (tmp_path / "release-marker.txt").write_text("ready\n", encoding="utf-8")
    assert main(["init", "--path", root, "--project-name", "Checker CLI"]) == 0
    assert (
        main(
            [
                "capture",
                "Ship a proof-backed release",
                "--path",
                root,
                "--description",
                "The release must include the required marker.",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "shape",
                "Require the release marker",
                "--path",
                root,
                "--description",
                "The release marker must be present in the project.",
                "--outcome",
                "OUT-001",
                "--proof-title",
                "Check the release marker",
                "--proof-description",
                "release-marker.txt must exist.",
                "--proof-checker-kind",
                "file_exists",
                "--proof-evaluation",
                "all",
                "--required-checker",
                "local.file-exists",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "check",
                "PRF-001",
                "--path",
                root,
                "--checker",
                "local.file-exists",
                "--config",
                '{"path":"release-marker.txt"}',
            ]
        )
        == 0
    )

    graph = GraphStore(tmp_path).load()
    assert graph.get_node("PRF-001").status == NodeStatus.VERIFIED.value
    assert graph.get_node("EVD-001").properties["checker"]["id"] == "local.file-exists"
    assert "PASS: Required path is present" in capsys.readouterr().out
