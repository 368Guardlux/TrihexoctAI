# TRIHEXΩ v2.0.0-alpha.5 — Component Release Notes

## Alpha.5 — Supervised learning and continuous evolution planning

- Added a hash-chained, append-only human-feedback ledger with strict schema and size limits.
- Added aggregate human-outcome diagnostics. Provisional approvals and unresolved outcomes are not treated as confirmed labels.
- Added deterministic, bounded candidate review-priority ranking. Scores allocate reviewer attention only; they are not threat probabilities.
- Added per-feed drift screening that holds unusual or unverifiable snapshots out of candidate discovery only, without changing production coverage.
- Expanded the advisory council to 16 staged role calls: 12 analysts, 3 critics, and 1 synthesis guardian.
- Added allowlisted aggregate calibration context to AI prompts; raw reviewer rationale and subscriber browsing data are not sent to the model provider.
- Added a deterministic evolution planner that creates a bounded engineering backlog from available operational reports.
- Added recurrence tracking; missing tasks are not automatically closed or deleted.
- Added planner state limits, missing-report semantics, and policy checks that prohibit code, rule, policy, trust, permission, or publication changes.
- Integrated planner output and state persistence into the read-only autonomous maintenance cycle.
- Added eight evolution-planner regression tests and direct command-line entry-point validation.
- Preserved all 16 production source modules and the 833-rule v1.3.2 filtering baseline.

## Alpha.4 — Operational assurance and permission separation

- Split production CI into a read-only build/validation job and a separate restricted publisher job.
- Added operations doctor, change-impact analyzer, and additional workflow/reporting checks.
- Preserved stable output unless deterministic checks and maintainer approval pass.

## Alpha.3 — Runtime policy and evidence integrity

- Enforced runtime policy caps and fail-closed configuration drift checks.
- Required curated publisher-group identity for advisory discovery; no feed-host fallback.
- Restricted AI-provider redirects to the configured endpoint host and capped timeouts.
- Rejected duplicate candidate findings and non-finite model confidence values.

## Alpha.2 — Candidate discovery and advisory council

- Added conservative discovery of exact host candidates from fresh, validated adblock feed changes.
- Required two registry-declared publisher groups; the labels are not proof of independent ownership or correctness.
- Added candidate pre-screening for protected and shared-hosting infrastructure.
- Added source-health history, read-only orchestration, and a twice-daily advisory workflow.
- Expanded the initial advisory roster and staged-review protocol.

## Alpha.1 — Initial TRIHEXΩ integration preview

- Added the first bounded advisory framework, conditional cache, adaptive fetch controller, rule provenance, human decision memory, and release-readiness checks.

## Preserved baseline

All 16 source modules and 833 authored unique active rules are preserved from v1.3.2. Alpha releases have not automatically added AI-generated production rules. The packaged filter list is an offline bootstrap unless separately regenerated and validated by a live production workflow.
