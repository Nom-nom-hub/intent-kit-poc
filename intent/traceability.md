# Traceability Map

| Source | Relation | Target |
|---|---|---|
| DEC-001 — Keep repository governance version-controlled | `addresses` | REQ-001 — Publish governed, licensed source |
| DEC-002 — Import source artifacts read-only with provenance | `addresses` | REQ-002 — Preserve reliable Spec Kit migration |
| DEC-003 — Record release evidence in the intent graph | `addresses` | REQ-003 — Require a reproducible local quality gate |
| EVD-001 — Local file existence: Required path is present: LICENSE. | `proves` | PRF-001 — Verify required governance artifacts |
| EVD-002 — Local file existence: Required path is present: SECURITY.md. | `proves` | PRF-001 — Verify required governance artifacts |
| EVD-003 — Local file existence: Required path is present: docs/speckit-import.md. | `proves` | PRF-002 — Verify importer guidance |
| EVD-004 — Local release quality gate | `proves` | PRF-003 — Record the latest full validation |
| REQ-001 — Publish governed, licensed source | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-001 — Publish governed, licensed source | `requires_proof` | PRF-001 — Verify required governance artifacts |
| REQ-002 — Preserve reliable Spec Kit migration | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-002 — Preserve reliable Spec Kit migration | `requires_proof` | PRF-002 — Verify importer guidance |
| REQ-003 — Require a reproducible local quality gate | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-003 — Require a reproducible local quality gate | `requires_proof` | PRF-003 — Record the latest full validation |

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
