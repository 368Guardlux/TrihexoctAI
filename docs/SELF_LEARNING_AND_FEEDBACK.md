# TRIHEXΩ Human-Feedback Learning and Evolution Contract

## What “self-learning” means here

Alpha.5 adds a bounded, supervised learning loop based on explicit human review outcomes. It is not autonomous model training, AGI, or a system that rewrites its own policies. The system learns operationally by retaining adjudicated outcomes, calculating aggregate category diagnostics, and adjusting the order in which candidates receive human review attention.

## Feedback decisions

- `approved_for_beta`: provisional trial approval; not counted as a confirmed outcome.
- `confirmed_effective_after_trial`: human-confirmed positive outcome after a controlled test.
- `rejected`: candidate rejected by a maintainer.
- `confirmed_false_positive_after_trial`: candidate caused or represented a confirmed false positive.
- `needs_more_evidence`: unresolved; excluded from the positive/negative denominator.

Only confirmed after-trial outcomes contribute to category diagnostic intervals. A small sample is marked insufficient. The system never interprets the rate as domain maliciousness or universal model accuracy.

## Ledger integrity

`reports/trihexomega-review-feedback.jsonl` is an append-only JSONL ledger. Every event records the previous event digest and its own SHA-256 digest. Verification detects accidental or unauthorized edits, deletions, reordering, and broken chain links. A hash chain is tamper-evident, not an identity signature; reviewer identity still depends on repository access controls and human review.

The ledger stores candidate and evidence hashes, category, decision, reviewer handle, and a short rationale. It must not contain browsing history, subscriber identifiers, passwords, session tokens, private URLs, or personal data.

## How to record an outcome

Record only after a human has actually adjudicated a candidate:

```bash
python tools/trihexomega/feedback_ledger.py record \\
  --ledger reports/trihexomega-review-feedback.jsonl \\
  --candidate-id CANDIDATE_ID \\
  --candidate-sha256 64_HEX_RULE_FINGERPRINT \\
  --category network \\
  --decision needs_more_evidence \\
  --reviewer YOUR_GITHUB_HANDLE \\
  --reason "Brief factual explanation"
```

Verify the chain and generate diagnostics:

```bash
python tools/trihexomega/feedback_ledger.py verify
python tools/trihexomega/feedback_ledger.py report
```

Commit reviewed ledger changes through a normal reviewed branch or pull request. Do not accept automated agent-authored feedback as human adjudication.

## What learning can change

- Candidate review order (bounded and deterministic).
- Which categories need more human evidence.
- Which recurring candidate classes merit an investigation.
- Aggregate diagnostics and reports.

## What learning cannot change

- Filter rules or source modules.
- Reference source identity or publisher grouping.
- Trust scores or coverage credit.
- Safety thresholds, release gates, agent permissions, or tool access.
- Stable publication decisions.

Any change to those items requires a separately reviewed code/configuration change and the normal deterministic test/release process.


## Evolution backlog integration

The deterministic `tools/trihexomega/evolution_planner.py` consumes the aggregate learning report alongside source-health, drift, discovery, swarm, and change-impact reports. Confirmed negative outcomes can trigger a category-specific compatibility investigation; insufficient samples can trigger a recommendation to collect more real human outcomes. These are engineering tasks, not automatic rule decisions. Recurrence is tracked across cycles and missing tasks are not automatically resolved.

The planner does not send raw ledger rationale to a model provider. The swarm receives only allowlisted aggregate category counts and uncertainty summaries. The ledger remains the source record and should be changed only through explicit human maintainer review.
