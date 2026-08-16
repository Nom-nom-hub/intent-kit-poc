# Design and Decision Record

**Project:** Checkout Safety

## Active Requirements

- **REQ-001 — Use idempotency keys** (`active`): Every confirmation request must carry an idempotency key and a repeated request must return the original order.

## Decisions

### DEC-001 — Use provider idempotency keys

**Status:** `proposed`  
**Rationale:** Provider-backed idempotency makes duplicate-order handling explicit and testable.  
**Addresses:** REQ-001 — Use idempotency keys  
**Alternatives considered:** Time-window deduplication

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
