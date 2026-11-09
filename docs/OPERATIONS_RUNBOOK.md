# TRIHEXΩ v2.0.0-alpha.5 — Operations Runbook

## Routine cycle

The autonomous workflow attempts a read-only maintenance and advisory cycle twice per day. GitHub scheduled execution is best-effort; it may be delayed or skipped by the platform.

The cycle performs, in order:

1. Validate runtime configuration and policy caps.
2. Fetch only the 32 registry-approved HTTPS reference feeds using bounded concurrency and verified conditional caching.
3. Write per-feed outcomes and update source-health history.
4. Compare verified feed snapshots with the discovery baseline. Large unexpected changes are held out of candidate discovery only.
5. Discover conservative candidate indicators from fresh, validated feed deltas.
6. Screen candidates for rule shape, publisher-group metadata, protected domains, and shared-hosting risk.
7. Verify the human-feedback hash-chain ledger and generate aggregate diagnostics.
8. Rank the eligible review queue for engineering attention only.
9. Optionally run the 16-role advisory council if the provider is configured and a non-empty candidate batch exists.
10. Generate a deterministic evolution backlog from available reports.
11. Save compact state and upload diagnostic artifacts; do not publish production rules.

## Key commands

```bash
python tools/validate_trihexomega_pack.py
python tools/validate_workflows.py
python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json
python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl
python -m unittest discover -s tests -v
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

## Important reports

- `trihexomega-feed-cache-report.json`: per-feed fetch and validator result.
- `trihexomega-source-health.json`: source-health diagnostics; no source is automatically removed or reweighted.
- `trihexomega-drift-report.json`: unusual source changes; holds affect advisory discovery only.
- `trihexomega-discovery-report.json`: new candidate observations.
- `trihexomega-policy-screen.json`: eligible versus held candidates.
- `trihexomega-learning-report.json`: aggregate confirmed human outcomes.
- `trihexomega-triage-report.json`: deterministic review ordering.
- `trihexomega-swarm-review.json`: optional LLM advisory output.
- `trihexomega-evolution-plan.json`: prioritized engineering actions.
- `trihexomega-evolution-state.json`: recurrence state; missing tasks are not auto-resolved.
- `trihexomega-cycle-report.json`: overall cycle status and stage durations.

## Manual advisory review

The autonomous-cycle workflow uploads the screened and ranked candidate bundle as
`trihexomega-candidates-<run-id>` after a successful run. To review it, open a
successful autonomous-cycle run on `main`, copy the numeric run ID from its URL,
then dispatch **TRIHEXΩ manual advisory candidate review** on `main` and provide
that ID. The workflow verifies the source run, downloads only its candidate
artifact, and stops with an explicit error if the bundle is missing or empty.
The source artifact is retained for 30 days. Dispatching the advisory workflow
from a non-main ref performs deterministic preflight only; it does not call the
configured model provider.

## Human feedback process

Only an authorized maintainer should record a decision after reviewing a candidate and, where applicable, completing a trial. Do not record AI recommendations as human outcomes. Provisional beta approval is not a confirmed positive label. Review `docs/SELF_LEARNING_AND_FEEDBACK.md` for the event taxonomy and privacy constraints.

## Evolution backlog process

Review recommendations in `trihexomega-evolution-plan.json` after each cycle. Use the task ID to track work in a normal GitHub issue or pull request. The planner records recurrence but intentionally does not close tasks. A maintainer must determine and document resolution.

## Failure handling

- If feed retrieval fails, inspect the exact per-feed errors and cache state. Do not count stale cache as fresh coverage.
- If drift is held, inspect the upstream change and explicitly review before any rebaseline.
- If the feedback ledger fails verification, preserve it and investigate; do not silently truncate or rebuild it.
- If model calls fail or return invalid output, candidates remain held. The deterministic maintenance path continues where possible.
- If validation or publication fails, preserve the last-known-good production artifact.
- Never weaken hard limits, protected-domain rules, or release gates just to make a workflow green.

## Release promotion

A stable release requires all deterministic tests and validators, source and rule provenance, compatibility evidence, a stable snapshot, change-impact review, and human maintainer approval. Test representative real websites in Brave before promotion. Static validation cannot prove zero breakage.

The production workflow applies the change-impact report as a strict gate. If it
holds a candidate, inspect `trihexomega-change-impact.json` from the diagnostics
artifact, then manually dispatch the workflow on `main` with
`accept_change_impact` enabled only if the held change is approved for further
review. For a large change, `accept_large_output_change` must also be enabled
after inspecting `rule-delta.json`. These acknowledgments do not publish by
themselves: configure the GitHub `production` environment with required
maintainer reviewers in repository settings. The publisher job is limited to
`main` and waits for that environment approval before receiving write access.
