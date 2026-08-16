# Changelog

All notable changes to Intent Kit are documented in this file.

The project follows [Semantic Versioning](https://semver.org/). Before `1.0.0`, minor releases may include breaking changes where necessary to clarify the experimental extension model.

## [Unreleased]

### Added

- A read-only Spec Kit importer for completed `spec.md`, optional `plan.md`, and optional `tasks.md` feature artifacts.
- Provenance-backed outcomes, requirements, decisions, and implementation tasks, including artifact SHA-256 digests and source-line references.
- The `intentkit import-speckit` command, importer documentation, generated implementation-task visibility, and migration regression coverage.
- Graph Insight commands: `intentkit drift` for provenance hash checks and `intentkit impact` for deterministic typed-path and proof-gap analysis.
- Read-only graph-insight documentation and a dependency-ordered public delivery roadmap.
- Local, version-controlled Policy Packs with shipped `release-critical`, `migration`, and `documentation` defaults.
- `intentkit policy` commands, policy-backed shaping defaults, graph-visible policy metadata, policy status summaries, and Policy Pack documentation.
- Controlled external checker execution through project-local allowlists, pinned manifests and entrypoints, a bounded JSON subprocess protocol, and `intentkit checker` management commands.

## [0.2.0] - 2026-08-16

### Added

- A local-first typed proof-checker foundation with `CheckRequest`, `CheckResult`, `CheckState`, and `ProofChecker` contracts.
- An explicit in-process checker registry and graph-safe proof runner.
- Immutable evidence recording with checker identity, version, execution metadata, configuration fingerprint, metrics, and artifacts.
- `latest`, `all`, `any`, and `manual` proof-evaluation policies.
- The `intentkit check` command, checker-aware proof shaping options, and the built-in `local.file-exists` checker.
- A comprehensive custom proof-checker extension guide.
- Public-release governance materials, reproducible quality checks, and a tracked end-to-end example.

### Changed

- Expanded package metadata, supported Python classifiers, and public repository discovery metadata.
- Clarified that Intent Kit is experimental and local-first; it is not yet a production-proof or untrusted-plug-in platform.

### Security

- Documented the trusted bundled-checker boundary and private vulnerability-reporting expectations.

## [0.1.0] - 2026-08-16

### Added

- Initial local-first Intent Graph Development proof of concept.
- Typed graph kernel with outcomes, requirements, decisions, proof obligations, evidence, and traceability links.
- Markdown renderer and CLI workflow for capturing intent, shaping work, manually recording proof, rendering, and status reporting.
