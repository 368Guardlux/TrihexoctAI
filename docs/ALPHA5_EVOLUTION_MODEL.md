# TRIHEXΩ Alpha.5 Evolution Model

## Controlled improvement loop

1. Fetch exact registry-approved HTTPS sources using conditional requests and verified cached representations.
2. Validate response identity, body size, encoding, format, freshness, and checksums.
3. Evaluate source health and per-feed content drift.
4. Hold anomalous or unverifiable snapshots out of advisory candidate discovery only.
5. Discover conservative exact third-party host candidates from fresh, validated feed deltas.
6. Screen candidates deterministically for protected services, shared hosting, rule scope, source identity, and evidence quality.
7. Verify the append-only human-feedback ledger and calculate aggregate, privacy-minimized diagnostics.
8. Rank candidate review effort using evidence freshness, completeness, source-label diversity, and category uncertainty. The score is not threat probability.
9. Run twelve specialist analysis roles, three critique roles, and one synthesis role using a bounded provider budget.
10. Convert available operational reports into a deterministic engineering-evolution backlog.
11. Track recurring issues across cycles without treating disappearance from a report as resolution.
12. Preserve the production filter list unless separately reviewed deterministic tests and human approval authorize a release.

## Self-learning scope

The project has a supervised operational learning loop. It accumulates explicit human outcomes, computes category-level diagnostic intervals, and can adjust the order in which candidates receive review attention. It can also prioritize recurring operational issues in its engineering backlog.

It does **not** autonomously train model weights, infer global trust from a small sample, rewrite source modules, modify agent prompts, change safety thresholds, add trusted feed identities, expand permissions, or self-publish rules. Feedback labels are not ground truth; provisional approvals are excluded from confirmed diagnostic counts.

## Evolution planner

`tools/trihexomega/evolution_planner.py` translates current doctor, source-health, feed, drift, learning, discovery, swarm, triage, and change-impact reports into a maximum-40-item prioritized engineering backlog. It records first-seen, last-seen, and recurrence counts. Missing tasks are marked `not_observed_this_cycle`; they are not auto-closed or deleted. The state file is bounded to 5,000 records and requires maintainer review before archival.

Priorities are engineering attention order only. They are not maliciousness scores or publication decisions. Missing and malformed input reports are marked unknown rather than healthy.

## AI terminology and limits

The review council consists of 16 role-specialized calls to one explicitly configured LLM-compatible endpoint per run: twelve analysts, three critics, and one synthesis guardian. Role prompts do not make independent minds, and shared-model agreement is not independent corroboration. This system is not AGI and makes no AGI claim.

The AI provider has no browsing, shell, repository, secrets, or production-write tools. It receives bounded candidate evidence and allowlisted aggregate feedback context, not raw reviewer rationale or subscriber browsing data.

## Safety invariant

When evidence, source identity, compatibility, policy, validation, or provider review is incomplete, the affected candidate remains held. Preserve the last known-good output. The production builder and publisher are separate from the advisory maintenance cycle.
