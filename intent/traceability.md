# Traceability Map

| Source | Relation | Target |
|---|---|---|
| DEC-001 — Keep repository governance version-controlled | `addresses` | REQ-001 — Publish governed, licensed source |
| DEC-002 — Import source artifacts read-only with provenance | `addresses` | REQ-002 — Preserve reliable Spec Kit migration |
| DEC-003 — Record release evidence in the intent graph | `addresses` | REQ-003 — Require a reproducible local quality gate |
| DEC-004 — Use deterministic bidirectional graph traversal | `addresses` | REQ-004 — Make change impact visible |
| DEC-005 — Run a minimal GitHub Actions quality matrix | `addresses` | REQ-005 — Enforce public continuous integration |
| DEC-006 — Keep policies declarative and local | `addresses` | REQ-006 — Apply risk-calibrated policies |
| DEC-007 — Use manifest-pinned JSON subprocesses | `addresses` | REQ-007 — Authorize controlled external proof checks |
| EVD-001 — Local file existence: Required path is present: LICENSE. | `proves` | PRF-001 — Verify required governance artifacts |
| EVD-002 — Local file existence: Required path is present: SECURITY.md. | `proves` | PRF-001 — Verify required governance artifacts |
| EVD-003 — Local file existence: Required path is present: docs/speckit-import.md. | `proves` | PRF-002 — Verify importer guidance |
| EVD-004 — Local release quality gate | `proves` | PRF-003 — Record the latest full validation |
| EVD-005 — Local file existence: Required path is present: docs/graph-insight.md. | `proves` | PRF-004 — Verify Graph Insight guidance |
| EVD-006 — Graph Insight v0.3.0 quality gate | `proves` | PRF-003 — Record the latest full validation |
| EVD-007 — GitHub Actions CI run 31973242959 | `proves` | PRF-005 — Verify successful public CI run |
| EVD-008 — Local file existence: Checker does not support this proof obligation. | `proves` | PRF-006 — Verify Apply risk-calibrated policies |
| EVD-009 — Policy Pack validation | `proves` | PRF-006 — Verify Apply risk-calibrated policies |
| EVD-010 — Policy Pack aggregation validation | `proves` | PRF-006 — Verify Apply risk-calibrated policies |
| EVD-011 — Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. | `proves` | PRF-007 — Verify Authorize controlled external proof checks |
| EVD-012 — Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. | `proves` | PRF-007 — Verify Authorize controlled external proof checks |
| EVD-013 — Intent Kit Example File Content: Required file and configured content are present: docs/external-checkers.md. | `proves` | PRF-007 — Verify Authorize controlled external proof checks |
| REQ-001 — Publish governed, licensed source | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-001 — Publish governed, licensed source | `requires_proof` | PRF-001 — Verify required governance artifacts |
| REQ-002 — Preserve reliable Spec Kit migration | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-002 — Preserve reliable Spec Kit migration | `requires_proof` | PRF-002 — Verify importer guidance |
| REQ-003 — Require a reproducible local quality gate | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-003 — Require a reproducible local quality gate | `requires_proof` | PRF-003 — Record the latest full validation |
| REQ-004 — Make change impact visible | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-004 — Make change impact visible | `requires_proof` | PRF-004 — Verify Graph Insight guidance |
| REQ-005 — Enforce public continuous integration | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-005 — Enforce public continuous integration | `requires_proof` | PRF-005 — Verify successful public CI run |
| REQ-006 — Apply risk-calibrated policies | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-006 — Apply risk-calibrated policies | `requires_proof` | PRF-006 — Verify Apply risk-calibrated policies |
| REQ-007 — Authorize controlled external proof checks | `derives_from` | OUT-001 — Sustain a trustworthy local-first Intent Kit release |
| REQ-007 — Authorize controlled external proof checks | `requires_proof` | PRF-007 — Verify Authorize controlled external proof checks |

## Manual Notes

<!-- intentkit:manual-notes:start -->
Add team context, review notes, or links here. This section is preserved on re-render.
<!-- intentkit:manual-notes:end -->
