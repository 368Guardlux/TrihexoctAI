# TRIHEXΩ v2.0.0-alpha.5 — Implementation and Operations

## Architecture summary

This alpha preserves the v1.3.2 deterministic filter builder and all sixteen production source modules. It adds a separate read-only maintenance, discovery, supervised-learning, advisory-intelligence, and engineering-evolution plane.

## Core sequence

1. Fetch approved HTTPS references with verified conditional caching and bounded adaptive concurrency.
2. Evaluate source health and per-feed drift.
3. Hold anomalous or unverifiable feed snapshots out of advisory discovery only.
4. Discover conservative exact third-party host candidates from validated feed deltas.
5. Screen candidates for source-group metadata, scope, protected services, and shared infrastructure.
6. Verify explicit human feedback and calculate aggregate diagnostics.
7. Rank candidate review effort; the score is not threat probability.
8. Run twelve analyst roles, three critics, and one synthesis guardian (maximum sixteen model calls, eight concurrent analysts).
9. Produce a deterministic engineering evolution plan with recurrence history.
10. Preserve production rules; require independent validation and human review for any proposed release.

## Important tools

- `cache.py`: conditional source retrieval and verified cache.
- `candidate_discovery.py`: delta-based candidate observations.
- `drift_guard.py`: source-drift screening for discovery only.
- `feedback_ledger.py`: human outcome ledger and integrity verification.
- `learning_engine.py`: review-priority adaptation from aggregate feedback.
- `swarm.py`: bounded sixteen-role language-model advisory review.
- `evolution_planner.py`: deterministic engineering backlog and recurrence history.
- `doctor.py`: local network-free diagnostics.
- `change_impact.py`: deterministic read-only filter-list diff analysis.
- `release_guard.py`: release-readiness requirements.

## Safe operation

The advisory workflow does not publish. It saves verified state and diagnostic artifacts. The production workflow uses read-only build/test permissions and a separate restricted publisher. Run all validators and tests before a development-branch workflow, then test representative sites in Brave. Never treat a local alpha package as proof of current live feed availability or browser compatibility.
