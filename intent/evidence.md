# Evidence Register

**Project:** Intent Kit

## Proof Obligations

### PRF-001 — Verify required governance artifacts

**Status:** `verified`
**Claim:** The license and security policy must be present in the repository.
**Evidence:**
- `pass` — **EVD-002**: Local file existence: Required path is present: SECURITY.md. (source: SECURITY.md)
- `pass` — **EVD-001**: Local file existence: Required path is present: LICENSE. (source: LICENSE)

### PRF-002 — Verify importer guidance

**Status:** `verified`
**Claim:** The public importer guide must be present with mapping and safety documentation.
**Evidence:**
- `pass` — **EVD-003**: Local file existence: Required path is present: docs/speckit-import.md. (source: docs/speckit-import.md)

### PRF-003 — Record the latest full validation

**Status:** `verified`
**Claim:** The current repository state must pass the documented local release quality gate.
**Evidence:**
- `pass` — **EVD-006**: Graph Insight v0.3.0 quality gate (source: local:ruff+pytest+build+installed-wheel+insight-smoke)
- `pass` — **EVD-004**: Local release quality gate (source: local:ruff+pytest+build+installed-wheel)

### PRF-004 — Verify Graph Insight guidance

**Status:** `verified`
**Claim:** The public Graph Insight guide must describe drift status, impact traversal, and proof-gap behavior.
**Evidence:**
- `pass` — **EVD-005**: Local file existence: Required path is present: docs/graph-insight.md. (source: docs/graph-insight.md)

### PRF-005 — Verify successful public CI run

**Status:** `verified`
**Claim:** The GitHub Actions CI workflow must complete successfully with the Python quality matrix and distribution smoke test.
**Evidence:**
- `pass` — **EVD-007**: GitHub Actions CI run 31973242959 (source: https://github.com/Nom-nom-hub/intent-kit-poc/actions/runs/31973242959)

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
