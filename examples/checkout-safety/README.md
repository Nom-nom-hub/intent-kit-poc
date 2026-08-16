# Checkout Safety Example

This tracked example demonstrates the smallest complete Intent Kit workflow: a product outcome becomes a requirement, a decision, a proof obligation, and a verified evidence record.

> **Example scope:** The checker validates the generated Intent Kit contract itself. It demonstrates the mechanics of local, reproducible proof recording; it does not connect to a real payment provider.

## What is included

| Location | Purpose |
|---|---|
| `.intent/graph.json` | Canonical graph with one outcome, requirement, decision, proof obligation, and evidence node. |
| `intent/intent.md` | Rendered outcome and requirement contract. |
| `intent/design.md` | Rendered decision record and alternative. |
| `intent/evidence.md` | Verified evidence produced by `local.file-exists`. |
| `intent/traceability.md` | Complete typed relationship map. |

## Re-run the proof

From the repository root, rerun the checker against the tracked example.

```bash
PYTHONPATH=src python -m intentkit check PRF-001 \
  --path examples/checkout-safety \
  --checker local.file-exists \
  --config '{"path":"intent/intent.md","contains":"Prevent duplicate orders"}'
```

The command records a new immutable evidence node, re-evaluates the proof obligation, and refreshes the rendered Markdown. Because the example is tracked, review its diff before committing a rerun.
