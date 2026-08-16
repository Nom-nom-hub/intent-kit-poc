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

### PRF-006 — Verify Apply risk-calibrated policies

**Status:** `verified`
**Claim:** Provide evidence that 'Apply risk-calibrated policies' satisfies the release-critical policy pack. Record explicit review or automated validation evidence. Evidence should be refreshed within 7 day(s) when the work changes.
**Policy:** `release-critical` (risk `R3`, evaluation `all`)
**Evidence freshness:** 7 day(s)
**Review:** Explicit review or automated validation evidence required.
**Evidence:**
- `pass` — **EVD-009**: Policy Pack validation (source: local:intentkit-policy+shape+status)
- `pass` — **EVD-010**: Policy Pack aggregation validation (source: local:policy-pack+aggregation)
- `skipped` — **EVD-008**: Local file existence: Checker does not support this proof obligation. (source: checker:local.file-exists)

### PRF-007 — Verify Authorize controlled external proof checks

**Status:** `verified`
**Claim:** Provide evidence that 'Authorize controlled external proof checks' satisfies the release-critical policy pack. Record explicit review or automated validation evidence. Evidence should be refreshed within 7 day(s) when the work changes.
**Policy:** `release-critical` (risk `R3`, evaluation `all`)
**Evidence freshness:** 7 day(s)
**Review:** Explicit review or automated validation evidence required.
**Evidence:**
- `pass` — **EVD-012**: Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. (source: docs/external-checkers.md)
- `pass` — **EVD-011**: Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. (source: docs/external-checkers.md)
- `pass` — **EVD-013**: Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. (source: docs/external-checkers.md)

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
