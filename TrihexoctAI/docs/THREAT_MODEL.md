# TRIHEXΩ v2.0.0-alpha.5 — Threat Model

## Assets

- Stable published filter list and metadata.
- Deterministic source modules and reference registry.
- Reference-feed cache and discovery baseline.
- Human-feedback ledger and review history.
- Model-provider credentials and workflow permissions.
- Production release integrity and legitimate website functionality.

## Threats and controls

| Threat | Risk | Controls |
|---|---|---|
| Malicious or compromised feed | Poisoned candidate data or misleading coverage | Exact registry allowlist, HTTPS, redirects restricted, format/size checks, checksums, drift guard |
| Prompt injection in feed/evidence | Agent follows instructions embedded in untrusted text | Treat all feed/evidence content as data; bounded schemas; no tools, browsing or shell |
| False-positive rule | Login, checkout, payment, video, or accessibility breakage | Exact-scope screening, protected-domain holds, adversarial compatibility review, browser testing |
| Shared-hosting collateral block | Unrelated tenants blocked | Shared-hosting detection and hold; no automatic scope escalation |
| Correlated reference sources | False impression of corroboration | Curated publisher-group metadata, lineage review; labels are not proof of independence |
| Model outage or malformed output | Incomplete review | Bounded time/tokens/calls; incomplete stage holds candidate; deterministic path continues |
| AI overreach | Unauthorized rule or policy change | No tool, shell, repository, secret, or publishing permissions; advisory-only outputs |
| Feedback poisoning | Misleading learning diagnostics | Human-only recording, schema limits, after-trial confirmed labels, hash-chain verification, small-sample warnings |
| Evolution-state corruption | Lost or misleading maintenance history | Schema/size caps, atomic writes, integrity checks and maintainer-reviewed archival |
| CI credential exposure | Unauthorized release changes | Read-only build job, separate restricted publisher, exact-commit check, SHA-256 artifact verification |
| Cache substitution | Unverified stale content treated as current | ETag/Last-Modified and SHA-256 validation; stale cache is not current coverage |
| Repeated agent calls / cost exhaustion | Excessive API cost | 16-call ceiling, 8 candidate cap, 8 concurrent analysis cap, timeout/token limits, no recursive spawning |

## Residual risks

Publisher IDs are curated labels, not cryptographic proof of independent ownership. Hash chains are tamper-evident, not digital signatures. Model agreement is not independent corroboration. Static policy tests cannot guarantee zero browser breakage. GitHub-hosted Actions, third-party actions, dependencies, and provider services remain external trust dependencies and require maintainer review.

## Privacy

No subscriber browsing history is collected. Raw reviewer rationale is not passed to the model provider. Workflow artifacts must not contain raw feed cache bodies or secrets. Review feedback should avoid personal or sensitive information.

## Safe failure

Unknown or incomplete evidence is held. Drift holds do not alter production feed coverage. Invalid feedback is not consumed. Failed tests cannot replace the last-known-good production artifact. No agent or planner may publish.
