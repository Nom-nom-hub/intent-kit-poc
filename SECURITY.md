# Security Policy

## Supported Versions

Intent Kit is pre-`1.0` software. Security fixes are applied to the latest release line only.

| Version | Supported |
|---|---|
| `0.2.x` | Yes |
| `< 0.2.0` | No |

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for a suspected security vulnerability. Instead, use GitHub’s private vulnerability reporting for this repository. If private reporting is unavailable, contact the repository owner through the GitHub profile associated with the project.

A report should include a clear description, affected version, reproduction steps or proof of concept, expected and actual behavior, and any relevant impact assessment. Do not include secrets, credentials, or private user data.

Maintainers will acknowledge valid reports, assess severity and scope, work on a fix, and coordinate disclosure where appropriate.

## Security Boundaries

Intent Kit is local-first and stores graph data in the project workspace. The `intentkit check` command currently loads **only trusted, in-process checkers bundled with Intent Kit**. It does not perform automatic external plug-in discovery or network-based checker installation.

Proof checkers should be treated as code-execution boundaries. They must not write graph state directly, must return bounded and redacted evidence, and must validate any configured project paths. The current built-in `local.file-exists` checker is deliberately restricted to project-contained paths.

External checker discovery, allowlisting, and isolated execution are planned improvements. Until those controls exist, do not add or enable untrusted checker code in a project intended for security-sensitive or business-critical proof workflows.
