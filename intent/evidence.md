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
- `pass` — **EVD-004**: Local release quality gate (source: local:ruff+pytest+build+installed-wheel)

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
