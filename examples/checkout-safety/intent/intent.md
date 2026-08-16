# Intent Contract

**Project:** Checkout Safety
**Graph updated:** 2026-08-16T16:06:16+00:00

## Outcomes

- **OUT-001 — Prevent duplicate orders** (`active`): Checkout retries must not create duplicate orders.

## Requirements

- **REQ-001 — Use idempotency keys** (`active`): Every confirmation request must carry an idempotency key and a repeated request must return the original order. Derived from: OUT-001 — Prevent duplicate orders.

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
