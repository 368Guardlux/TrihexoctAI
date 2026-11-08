# TRIHEXΩ v2.0.0-alpha.5 — All-in-One Architecture and Engineering Blueprint

## 1. Mission

TRIHEXΩ extends the deterministic TrihexoctAI / Guardlux filter project with evidence-driven maintenance, supervised learning diagnostics, bounded language-model review, source-drift screening, and a controlled evolution backlog. Its target is reliable filtering with minimal collateral damage—not the largest possible blocklist, unrestricted autonomy, or claims of artificial general intelligence.

**Core invariant:** no AI, discovery, learning, or evolution-planning component can directly modify production rules, policies, trusted source identities, release thresholds, permissions, or published artifacts.

## 2. Baseline preserved

- Version: `2.0.0-alpha.5`.
- Source modules: 16, byte-identical to the supplied v1.3.2 archive.
- Authored unique active rules: 833, unchanged.
- Configured reference feeds: 32.
- Network rules: 662.
- URL-parameter rules: 77.
- Cosmetic rules: 85.
- Path/regex rules: 9.

The local archive is an offline bootstrap. Its metadata does not establish current online availability of the 32 feeds. The 833 authored-rule count is distinct from any external reference coverage count.

## 3. Architecture planes

### 3.1 Filtering plane

`src/modules/`, `tools/build_filter.py`, and `tools/validate_filter.py` form the deterministic production filtering path. They normalize and validate rules, audit duplication and policy, and generate `Trihexoct.txt` and metadata. This plane does not consume AI outputs as executable policy.

### 3.2 Maintenance plane

`cache.py` fetches registry-approved HTTPS sources using conditional request validators, a verified cache, bounded retries, and capped adaptive concurrency. A 304 response is usable only when the cached body matches its metadata and checksum. Stale cache does not count as fresh coverage.

### 3.3 Discovery plane

`candidate_discovery.py`, `policy_engine.py`, and `drift_guard.py` identify conservative candidate indicators from fresh, validated adblock feed deltas. Discovery uses curated publisher IDs as registry annotations, not proof of editorial independence. Multiple feeds assigned to one publisher ID count as one group. Shared hosting, protected services, ambiguous scope, and stale evidence are held.

### 3.4 Learning plane

`feedback_ledger.py` records explicit human outcomes in append-only JSONL with a SHA-256 hash chain. `learning_engine.py` computes aggregate category diagnostics and review-priority ordering. It never trains model weights or changes rules, trust, policy, or release authority.

### 3.5 Intelligence plane

`swarm.py` implements a 16-call staged review council: twelve analysis roles, three critics, one synthesis guardian. At most eight calls are concurrent during analysis. The model endpoint is optional, bounded, and used through HTTPS. The agents receive small validated candidate bundles and allowlisted aggregate learning context, not raw feeds, private reviewer rationale, or subscriber browsing history.

### 3.6 Evolution and assurance plane

`evolution_planner.py`, `doctor.py`, `change_impact.py`, `release_guard.py`, validators, tests, and workflows convert operational evidence into recommended engineering work. Reports are advisory and never authorize publication. The planner preserves recurring task observations and does not auto-close missing tasks.

## 4. Controlled self-learning

### 4.1 Learning inputs

Only explicitly recorded human adjudications enter the feedback ledger. Decisions include provisional beta approval, confirmed effective after trial, rejection, confirmed false positive after trial, and needs more evidence. Provisional and unresolved decisions are excluded from confirmed label diagnostics.

### 4.2 Learning outputs

- Aggregate category-level outcome counts and intervals.
- Identification of categories with insufficient adjudicated sample size.
- Bounded changes to review ordering only.
- Engineering recommendations when repeated false positives or unresolved categories appear.

### 4.3 Learning exclusions

- No automatic model-weight training.
- No automatic global reputation or trust scoring.
- No automatic rule insertion or deletion.
- No automatic policy or threshold changes.
- No source identity or publisher-label changes.
- No subscriber browsing-history collection.
- No AI-authored human feedback.

A feedback ledger is tamper-evident, not an identity signature or cryptographic proof that a reviewer was correct. Human identity relies on repository access controls and review procedures.

## 5. Adaptive source drift

`drift_guard.py` compares current fresh verified cached adblock rules against the prior discovery baseline. A large delta or unverifiable snapshot is held out of candidate discovery. It does not alter the separate production feed report or production builder. Automatic rebaseline is disabled. A maintainer must inspect upstream changes and explicitly decide whether to rebaseline.

## 6. Evidence and candidate model

Candidate discovery is restricted to new exact third-party host rules observed in changed, validated adblock-format feeds. It uses across-run observations and two curated publisher-group labels before advisory queueing. The labels are metadata, not proof of independent sources. The candidate pre-screen excludes common functional services, shared-hosting platforms, ambiguous or broad scopes, unsupported URL-to-domain escalation, and untrusted data. Candidates are capped at eight per run; evidence items are capped at eight per candidate.

## 7. Sixteen-role advisory council

### Analysis stage — 12 bounded roles

1. Source integrity.
2. Threat evidence.
3. Filter semantics.
4. Domain context.
5. False-positive risk.
6. Browser compatibility.
7. Coverage and redundancy.
8. Privacy and data minimization.
9. Performance impact.
10. Accessibility and service continuity.
11. Source lineage and editorial-independence caveats.
12. Indicator granularity and scope escalation.

### Critique stage — 3 bounded roles

13. Adversarial critic.
14. Functional-safety and compatibility critic.
15. Evidence-counterfactual and uncertainty critic.

### Synthesis stage — 1 bounded role

16. Release-readiness synthesis guardian. It identifies blockers and review needs; it cannot approve publication.

All roles may share the same model provider and model family. More prompts do not create AGI or independent minds. Consensus is not proof. The workflow is capped at sixteen calls, eight simultaneous analysis calls, eight candidates, eight evidence items per candidate, 45 seconds per call, and 1,400 response tokens per role.

## 8. Deterministic evolution planner

`evolution_planner.py` reads the Operations Doctor, cycle report, feed cache report, source-health report, drift report, learning report, swarm report, discovery report, triage report, and change-impact report.

It creates up to 40 engineering recommendations with stable IDs, triggers, actions, acceptance criteria, priority, first-seen and last-seen timestamps, and recurrence counts. Priorities are maintenance attention order, not threat scores.

A task absent from the latest report is retained as `not_observed_this_cycle`. It is never automatically resolved or deleted. State is limited to 5,000 task records and 2 MB; exceeding limits stops the planner and requires maintainer-reviewed archival.

The planner has no network access, model calls, shell execution, source write, rule write, policy write, trust modification, permission modification, or publication authority.

## 9. Performance and speed

- Conditional HTTP requests avoid re-downloading unchanged resources when validators are supported.
- SHA-256 verifies cache-body integrity.
- Adaptive fetch concurrency is capped at eight workers.
- Retry budgets and backoff are bounded.
- Registry order is preserved in output for reproducibility.
- Duplicate content can be reused only through verified cache metadata.
- AI calls are skipped for empty queues and when the optional provider is absent.
- Model review is capped and staged; no recursive agent spawning is allowed.

Speed is measured, not assumed. Faster completion is not allowed to weaken source validation or regression gates. A 304 response is not evidence of content validity unless the associated cached body and identity are verified.

## 10. Security and privacy boundaries

- Feed data and candidate evidence are untrusted and never executed.
- Provider redirects are limited to the configured host allowlist.
- API credentials are GitHub Actions secrets and never enter logs or candidate bundles.
- Model output is bounded, schema-validated, and cross-checked against known candidate/evidence IDs.
- Agents have no browser, shell, repository, secrets, or publication tools.
- Raw reviewer rationale is not sent to the model provider.
- No subscriber browsing history is collected.
- CI build and test steps use read-only permissions; a separate publisher job receives write only after successful validation, source-commit checks, and artifact checksum verification.

## 11. Website compatibility and false-positive controls

Blocking a host can affect unrelated services on shared infrastructure. Exact host indicators are not automatically escalated to registrable-domain blocks. Generic consent, cookie, login, authentication, checkout, payment, accessibility, navigation, or modal elements must not be hidden with broad cosmetic selectors. Candidates that can plausibly break core functionality are held for review.

Static validation cannot guarantee zero website breakage. Test the resulting stable list in Brave against representative pages for search, login, checkout, payment, video, embedded media, accessibility, and ordinary navigation.

## 12. CI/CD and release topology

### Production workflow

The production workflow separates read-only build/validation from a restricted publisher job. The publisher checks out the exact triggering commit, verifies the artifact checksum manifest, and refuses to publish if the source commit advanced or the artifact is inconsistent.

### Autonomous maintenance workflow

The twice-daily best-effort workflow restores compact verified cache and evolution state, validates the package, tests the project, verifies the feedback ledger, runs read-only maintenance and discovery, optionally runs the swarm, generates the evolution plan, saves compact state, and uploads bounded reports. It never publishes production filter rules.

## 13. Local acceptance commands

```bash
python -m pip install --disable-pip-version-check --requirement requirements-ci.txt
python tools/validate_trihexomega_pack.py
python tools/validate_workflows.py
python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json
python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl
python -m unittest discover -s tests -v
python tools/audit_source_modules.py --output reports/source-inventory.json
python tools/build_filter.py --output /tmp/Trihexoct-alpha5-test.txt --report /tmp/trihexoct-alpha5-report.json
python tools/validate_filter.py /tmp/Trihexoct-alpha5-test.txt
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

## 14. Alpha.5 release boundaries

This is a development alpha. The package has local regression and structural checks, but does not prove current 32-feed availability, real model-provider quality, long-term GitHub scheduled-run reliability, Brave engine compatibility, or zero website breakage. The packaged filter metadata is offline bootstrap. The 833 rules remain the original v1.3.2 authored set.

## 15. Promotion checklist

1. Preserve stable v1.3.2 as a recoverable baseline.
2. Upload alpha.5 to a separate development branch.
3. Run local package, workflow, and regression validation.
4. Run GitHub-hosted maintenance and inspect every configured feed.
5. Inspect drift, health, discovery, learning, swarm, and evolution-plan reports.
6. Configure an AI provider only if desired; review data processing and cost.
7. Run real Brave compatibility tests.
8. Inspect CI permissions, branch protection, cache persistence, and rollback.
9. Require independent maintainer review and explicit approval.
10. Promote only after all release gates pass.
