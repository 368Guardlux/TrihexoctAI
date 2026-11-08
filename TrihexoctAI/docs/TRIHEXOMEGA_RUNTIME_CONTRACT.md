# TRIHEXΩ Runtime Contract — v2.0.0-alpha.5

## Runtime identity

The package, agent registry, policy, source registry, and hard-coded runtime limits must agree before the maintenance or advisory cycle starts. Configuration drift fails closed.

## Fixed specialist review limits

- 16 total roles: 12 analysts, 3 critics, and 1 synthesis guardian.
- Maximum 16 model calls per non-empty review batch.
- Maximum 8 simultaneous analysis calls.
- Maximum 8 candidates per batch and 8 evidence items per candidate.
- Maximum 45 seconds per model call and 1,400 response tokens per role.
- One configured HTTPS OpenAI-compatible provider endpoint per run.
- Missing or partial results hold affected candidates.

## Permissions

The swarm has no browser, shell, repository, secret, or production-publication tools. The learning engine can adjust review order only. The evolution planner creates backlog reports only. Neither can edit source modules, rules, reference identities, trust, policy thresholds, agent permissions, workflows, or releases.

## Source and drift policy

Candidate discovery requires fresh validated adblock feed deltas and at least two curated publisher-group labels. Labels do not prove independent ownership or editorial independence. Unverifiable cache state and large feed deltas are held out of candidate discovery. Drift holds never alter production coverage.

## Release requirements

Every proposed production change must pass current source audit, filter policy validation, regression testing, change-impact review, compatibility review, last-known-good snapshot checks, and explicit human maintainer approval. Advisory output is never production authorization.
