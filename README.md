# Trihexoct Guardlux — TRIHEXΩ v2.0.0-alpha.5

**Project version:** `2.0.0-alpha.5`  
**Release channel:** Development alpha / integration preview  
**Stable production subscription:** 'https://raw.githubusercontent.com/368Guardlux/TrihexoctAI/main/Trihexoct.txt'
**Target filtering engine:** Brave Shields / supported ABP-style filtering syntax

TRIHEXΩ is an expanded, evidence-driven maintenance and assurance architecture around the existing deterministic Trihexoct filter project. Alpha.5 preserves the v1.3.2 source modules and the 833-rule authored baseline while adding human-feedback diagnostics, source-drift screening, adaptive review triage, and a deterministic engineering-evolution planner.

> **Status and terminology:** This is not AGI, not autonomous model training, and not an unrestricted self-modifying system. The optional review council is a bounded multi-agent language-model workflow. Its role prompts provide task specialization; they do not create independently trained minds. Human feedback can improve aggregate diagnostics and review ordering only. No AI or planner component may edit production rules, alter trust or release policy, or publish.

## 1. What this project does

Trihexoct Guardlux is a supplementary filter-list project. Its deterministic builder normalizes, audits, validates, and compiles curated source modules into a published filter list. Approved reference feeds support source-health and overlap analysis under configured policy. They are not copied wholesale into the output, and the advisory discovery system does not automatically add their rules to production.

The engineering objective is not to maximize the number of rules. It is to maintain useful, evidence-backed coverage while minimizing false positives, preserving legitimate website functionality, and keeping every release traceable and recoverable.

## 2. Preserved v1.3.2 baseline

| Baseline measurement | Value |
|---|---:|
| Source modules | 16 |
| Authored unique active rules | 833 |
| Configured reference feeds | 32 |
| Network rules | 662 |
| URL-parameter rules | 77 |
| Cosmetic rules | 85 |
| Path/regex rules | 9 |

All 16 source-module files are preserved byte-for-byte from the supplied v1.3.2 archive. The 833 authored rules are unchanged. The packaged `Trihexoct.txt` is a locally generated offline-bootstrap artifact; creating this archive did not fetch all 32 live feeds or establish current online coverage.

The 833 count describes the unique authored source inventory. It must not be conflated with external reference coverage or the number of indicators observed across reference feeds.

## 3. Alpha.5 additions

### 3.1 Human-feedback learning ledger

`tools/trihexomega/feedback_ledger.py` records explicit maintainer outcomes in an append-only JSONL ledger with a SHA-256 hash chain. Events contain a candidate identifier and fingerprint, category, decision, reviewer handle, evidence hashes, and a short rationale.

Only after-trial human outcomes are counted as confirmed diagnostic labels. Provisional approval and unresolved outcomes are not ground truth. The ledger is tamper-evident, not an identity signature. It does not collect subscriber browsing history.

### 3.2 Learning-informed review prioritization

`tools/trihexomega/learning_engine.py` combines evidence freshness, completeness, curated publisher-label count, and category-level sample uncertainty to order candidate review work. The score is an **engineering review-priority score**, not maliciousness, threat probability, model confidence, or a decision to block.

Feedback can influence review order and diagnostic attention only. It cannot change rules, source identities, trust weights, safety thresholds, agent permissions, or release authority.

### 3.3 Per-feed drift guard

`tools/trihexomega/drift_guard.py` compares fresh, verified cached feed snapshots with the discovery baseline. Unusually large changes are held out of candidate discovery pending investigation.

A drift hold affects the advisory discovery input only. It does not change production feed coverage, disable a reference feed in the deterministic production builder, delete source history, or trigger automatic rebaselining. Missing or mismatched cache data is held rather than treated as fresh evidence.

### 3.4 Deterministic evolution planner

`tools/trihexomega/evolution_planner.py` turns available operations, source-health, drift, learning, discovery, swarm, triage, and change-impact reports into a bounded engineering backlog. It identifies actionable follow-ups such as unresolved source drift, incomplete feed retrieval, feedback-integrity problems, repeated false-positive outcomes, and incomplete AI reviews.

The planner records recurrence across maintenance cycles so repeated operational issues remain visible. A missing recommendation in a later cycle is not automatically considered resolved. Recommendations are engineering attention priorities, not threat scores. The planner does not modify source code, rules, policies, source trust, permissions, or releases.

### 3.5 Expanded advisory council

The optional review council has 16 bounded role calls per non-empty candidate batch:

- 12 specialist analysis roles;
- 3 critique roles, including adversarial, functional-safety, and evidence-counterfactual review;
- 1 synthesis guardian.

At most 8 analysis calls run concurrently. A batch is capped at 8 candidates and each candidate at 8 evidence items. Each model call is capped at 45 seconds and 1,400 response tokens. The system uses one explicitly configured HTTPS OpenAI-compatible endpoint per run unless the implementation is deliberately changed and revalidated. Role specialization is not model independence. Agreement is not proof.

The council has no external browsing, shell, repository-write, secret-reading, or production-publication tools. Missing, malformed, contradictory, or incomplete review results cause candidates to remain held.

## 4. Retained capabilities from earlier alpha releases

- Conditional HTTP requests with ETag and Last-Modified support.
- Verified HTTP 304 cache reuse; stale or mismatched cache entries do not count as fresh coverage.
- SHA-256 cache-integrity checks and atomic cache writes.
- Bounded adaptive fetch concurrency (maximum 8 workers) and retry controls.
- Registry-declared publisher IDs; multiple feeds from one curated publisher group count once for discovery corroboration.
- Candidate discovery from changed, validated adblock-format feed snapshots.
- Protected-domain and shared-hosting screening.
- Per-feed and per-publisher health diagnostics; health history does not automatically disable or reweight sources.
- Rule provenance and deterministic filter change-impact analysis.
- Network-free Operations Doctor.
- Last-known-good release and output-delta safeguards.
- Production workflow separation: a read-only build/validation job and a separate restricted publisher job that verifies the exact triggering commit and artifact checksums.
- A separate twice-daily read-only maintenance/discovery/advisory workflow. GitHub scheduled runs are best-effort and may be delayed.

## 5. Architecture

TRIHEXΩ is separated into six planes:

1. **Filtering plane:** deterministic source modules, normalization, policy checks, compilation, and the stable output.
2. **Maintenance plane:** approved HTTPS feed fetching, conditional caching, integrity validation, bounded concurrency, and source-health diagnostics.
3. **Discovery plane:** fresh feed-delta observations, publisher-group annotations, per-feed drift screening, and deterministic candidate pre-screening.
4. **Learning plane:** hash-chained human-feedback outcomes, aggregate calibration diagnostics, and bounded review-priority adaptation.
5. **Intelligence plane:** optional 16-role language-model review of a small, schema-validated candidate bundle.
6. **Evolution and release-assurance plane:** deterministic engineering backlog, regression tests, change-impact analysis, human review, last-known-good protection, and controlled publication.

The maintenance, discovery, learning, intelligence, and evolution-planning components do not edit the production filter list. The production builder and publisher remain separate.

## 6. Continuous improvement model

The intended controlled cycle is:

1. Fetch only registry-approved HTTPS sources.
2. Verify cache identity, checksums, validators, and content format.
3. Evaluate health and source drift.
4. Discover only conservative candidate indicators from fresh validated deltas.
5. Screen candidates for rule scope, protected services, and shared infrastructure.
6. Verify the human-feedback ledger and calculate aggregate diagnostics.
7. Rank candidates for review effort without estimating threat probability.
8. Run the bounded advisory council only when candidates exist and a provider is configured.
9. Generate an engineering-evolution plan from machine-readable operational reports.
10. Preserve the current stable release unless separately reviewed deterministic gates and human approval authorize a candidate release.

This is controlled, supervised operational learning—not autonomous retraining, code self-modification, or AGI. The project can continue deterministic maintenance if the model provider is unavailable.

## 7. Automation and reports

The autonomous workflow attempts a maintenance and advisory cycle twice daily. Scheduled execution is best-effort. It restores verified cache and compact state, validates the package, runs the test suite, verifies the human-feedback ledger, runs the read-only orchestrator, saves state, and uploads bounded diagnostics. It does not commit or publish the production filter list.

Important reports include:

- `trihexomega-cycle-report.json`
- `trihexomega-feed-cache-report.json`
- `trihexomega-source-health.json`
- `trihexomega-drift-report.json`
- `trihexomega-discovery-report.json`
- `trihexomega-policy-screen.json`
- `trihexomega-learning-report.json`
- `trihexomega-triage-report.json`
- `trihexomega-swarm-review.json`
- `trihexomega-evolution-plan.json`
- `trihexomega-doctor.json`
- `trihexomega-change-impact.json`

Raw feed-cache bodies must not be uploaded as public artifacts. Review feedback rationale is not sent to the model provider; only allowlisted aggregate context is passed to the swarm.

## 8. Local validation

Use Python 3.12 or a compatible supported Python version. Install the bounded CI dependencies and run:

```bash
python -m pip install --disable-pip-version-check --requirement requirements-ci.txt
python tools/validate_trihexomega_pack.py
python tools/validate_workflows.py
python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json
python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl
python -m unittest discover -s tests -v
python tools/audit_source_modules.py --output reports/source-inventory.json
python tools/build_filter.py --output /tmp/Trihexoct-alpha5-test.txt --report /tmp/trihexoct-alpha5-test-report.json
python tools/validate_filter.py /tmp/Trihexoct-alpha5-test.txt
```

To create the deterministic evolution backlog from reports already present in `reports/`:

```bash
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

The evolution planner treats missing or malformed reports as unknown, not healthy. It never creates automatic code or rule changes.

## 9. Optional AI-provider configuration

AI review is disabled unless both `TRIHEXOMEGA_AI_API_KEY` and `TRIHEXOMEGA_AI_MODEL` are configured. Store the key only as a GitHub Actions secret. The configured HTTPS endpoint must support the expected OpenAI-compatible JSON chat-completions response. Review the provider's data-processing terms, retention, latency, and cost before enabling it. Never put credentials in files, candidate bundles, issues, commits, or logs.

One configured model endpoint is used per run in this release. Multiple role prompts do not provide independent model corroboration. The system must not claim AGI or treat model confidence as verified truth.

## 10. Safety and compatibility commitments

- No AI-generated rule is inserted into production automatically.
- No AI component can edit or publish source modules, policy, workflows, secrets, or stable artifacts.
- No feed content is executed and no instructions embedded in external content are trusted.
- URL indicators are not escalated to domain-wide blocks without separate domain-level evidence.
- Shared hosting, CDNs, identity, payment, checkout, authentication, and essential site functionality require conservative treatment.
- Generic consent, login, payment, accessibility, modal, or navigation elements must not be hidden with broad cosmetic selectors.
- A source-health or drift finding never silently removes a feed from the production builder.
- Missing evidence, incomplete review, failed tests, or uncertain change impact results in hold.
- The stable release must remain recoverable and must not be overwritten after failed validation.
- The project does not collect subscriber browsing history.

No filter list can guarantee zero website breakage. Representative real-browser testing in Brave is required before production promotion.

## 11. Alpha.5 limitations

- The packaged metadata is an offline bootstrap; archive creation did not fetch or certify the 32 live reference feeds.
- The optional AI provider must be configured and tested; no model credentials are included.
- The swarm is an advisory LLM workflow, not AGI or autonomous self-training.
- Human feedback influences diagnostics and review ordering only; it does not train model weights or mutate rules.
- The evolution planner creates a backlog only; it does not autonomously implement changes or close tasks.
- Static tests do not establish real Brave engine compatibility or zero false positives.
- GitHub Actions workflow parsing and local validation do not replace an actual GitHub-hosted run.

## 12. Safe integration

1. Back up the current stable v1.3.2 repository.
2. Upload this complete project folder to a separate development branch.
3. Preserve the entire root layout, including `.github/`, `config/`, `docs/`, `reports/`, `src/`, `tests/`, and `tools/`.
4. Run all local validation commands above.
5. Inspect the workflow permissions and repository settings.
6. Run the autonomous maintenance workflow and examine all 32 per-feed results.
7. Configure the optional model provider only after reviewing provider privacy and cost.
8. Test representative Brave sites and essential functionality.
9. Require maintainer approval, a stable snapshot, compatibility evidence, and passing deterministic gates before any production promotion.

The production subscription URL remains unchanged. This archive is a development alpha and has not been deployed to the live repository.
