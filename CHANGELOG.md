## TRIHEXΩ v2.0.0-alpha.5

- Added a tamper-evident human-feedback ledger with aggregate, privacy-minimized learning diagnostics.
- Added learning-informed review-priority ranking; historical outcomes do not change threat decisions or production rules.
- Added discovery-only per-feed drift screening that holds anomalous sources out of candidate discovery without changing production coverage.
- Expanded the advisory council to sixteen bounded role calls: twelve analysts, three critics, and one synthesis guardian.
- Integrated verified feedback calibration context into bounded AI prompts while excluding raw reviewer rationale.
- Added direct CLI tools and tests for feedback verification, drift screening, learning diagnostics, and adaptive triage.
- Added a deterministic evolution planner that converts operational reports into a bounded engineering backlog with stable task IDs, acceptance criteria, and recurrence tracking.
- Preserved historical task records across cycles; missing recommendations are marked not observed, never auto-resolved or silently deleted.
- Integrated the evolution planner into the read-only orchestrator and persisted its bounded state through the autonomous workflow cache.
- Added workflow verification of the human-feedback ledger before learning diagnostics are consumed.
- Rewrote current release documentation and the master blueprint to align with the sixteen-role council and alpha.5 behavior.
- Preserved all sixteen source modules and the 833-rule production baseline.

## 2.0.0-alpha.4 — Advanced Operations and Change-Impact Layer

- Split production CI into read-only build/validation and a separate publisher-only write job; the publisher verifies the triggering commit and SHA-256 payload before committing.
- Added local network-free operations doctor and deterministic filter change-impact reports to maintenance workflows.
- Added local network-free operations doctor for layout, version, feed registry identity, and runtime-policy diagnostics.
- Added read-only filter change-impact analysis with category deltas, duplicate detection, broad-scope rule flags, global cosmetic warnings, and manual-review recommendations.
- Added alpha4 regression tests for doctor behavior and high-risk/large filter diffs.
- Preserved all production source modules and filtering rules; AI still cannot write or publish production artifacts.
- Added explicit reminder that role-specialized LLMs are not AGI and that provider configuration is required.

## 2.0.0-alpha.3 — 2026-11-08 — Runtime policy and evidence-integrity hardening

- Made the policy file an enforced runtime contract for the orchestrator and swarm; code, agent roster, policy, and candidate caps now fail closed when they drift.
- Aligned candidate/evidence/model-call/parallelism/timeout/token budgets across the policy, role registry, runtime, and pack validator.
- Made missing publisher identity explicitly unclassified; feed hostnames are no longer substituted for publisher identity in candidate discovery or health rollups.
- Enforced curated publisher-group thresholds and source-discovery limits from the same validated policy used by the swarm.
- Restricted AI-provider redirects to the configured endpoint hostname so bearer credentials are not forwarded to an unrelated host.
- Enforced the configured 45-second model-call ceiling; environment overrides cannot enlarge it.
- Rejected duplicate candidate findings and non-finite model confidence values.
- Added fail-closed tests for policy drift, unsafe production permissions, missing publisher identity, model-output integrity, provider redirect boundaries, and timeout caps.
- Preserved the original sixteen source modules and the 833-rule baseline; alpha.3 adds no unreviewed production filtering rules.

This remains an integration alpha. The bounded LLM review swarm is not AGI, has no tools or repository permissions, and cannot publish production changes. Live 32-feed execution and Brave compatibility remain to be verified after deployment to a development branch.

# Changelog

## 2.0.0-alpha.2 — 2026-11-08 — TRIHEXΩ expanded cognitive maintenance preview

- Preserved all sixteen source modules and the existing deterministic filtering rule set.
- Expanded the bounded advisory roster from eight to twelve staged specialist roles: ten analysis roles, one adversarial critic, and one release synthesis guardian.
- Added staged completeness checks and conservative aggregation; incomplete/missing reviewer output holds candidates.
- Reduced the maximum candidate batch to eight to keep model responses within the configured output budget.
- Added delta-based candidate discovery from fresh validated `adblock` feed snapshots; the first cycle seeds a baseline and emits no candidates.
- Added multi-host observation tracking, a 45-day pending evidence window, and a reviewed-candidate fingerprint ledger.
- Added deterministic candidate policy screening for protected services, shared-hosting infrastructure, narrow rule shape, and evidence-host diversity.
- Added rolling source-health history and diagnostics without automatic source removal/reweighting.
- Added curated publisher IDs for the 32-feed registry; candidate corroboration now counts distinct publisher groups rather than feed hostnames.
- Added per-publisher health rollups for diagnostics only; publisher labels do not prove ownership or independence and do not change feed weights.
- Corrected review suppression so only candidates that actually reached the AI swarm are marked reviewed.
- Added a unified read-only orchestrator and twice-daily GitHub Actions cycle with state caching and report artifacts.
- Added an expanded architecture, operations, threat-model, AGI-reality, and integration documentation set.
- Added regression coverage for discovery, policy screening, health history, and the twelve-call mocked swarm protocol.
- AI remains advisory-only. No production rules or output are modified by AI.

## 2.0.0-alpha.1 — 2026-11-08 — TRIHEXΩ initial integration preview

- Re-versioned the full bundle as v2.0.0-alpha.1.
- Added the initial eight-role bounded AI advisory framework.
- Added conditional HTTP cache, adaptive fetch concurrency, rule provenance, human decision memory, and release readiness checks.
- Added integration and security documentation.

## 1.3.2 — Baseline

- Existing deterministic filtering builder, sixteen source modules, thirty-two configured reference feeds, source validation, output-delta checks, and production workflow.
