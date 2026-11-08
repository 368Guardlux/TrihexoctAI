# TRIHEXΩ Deterministic Evolution Planner

## Purpose

The evolution planner converts structured maintenance evidence into a prioritized engineering backlog. It is intended to make improvement work continuous, traceable, and less dependent on manually re-reading every report after each scheduled cycle.

## Inputs

The planner reads available reports from `reports/`:

- Operations Doctor;
- cycle summary and required-source-group gaps;
- feed-cache and source-health results;
- per-feed drift report;
- human-feedback learning report;
- candidate discovery and triage reports;
- AI swarm review report;
- filter change-impact report.

A missing or malformed report is represented as unknown. It is not interpreted as a healthy result.

## Outputs

- `reports/trihexomega-evolution-plan.json`: current prioritized recommendations.
- `reports/trihexomega-evolution-state.json`: bounded recurrence history.

Each task includes a stable ID, trigger, recommended action, acceptance criteria, priority, first/last observation timestamps, and recurrence count. Priority is engineering attention order, not threat probability.

## Recurrence and closure

A task observed in repeated cycles receives a higher recurrence count. If it is absent from a later report, its stored state is retained and marked `not_observed_this_cycle`. The planner does not close, delete, or resolve it automatically. Maintainers decide whether work is resolved and record that disposition through the project's reviewed maintenance process.

The state is limited to 5,000 task records and 2 MB. If either limit is exceeded, the planner stops and asks for maintainer-reviewed archival rather than silently truncating history.

## Permissions

The planner is deterministic and local. It has no network access, does not call an LLM, and does not modify source modules, filter rules, reference identities, trust settings, model weights, policies, release thresholds, workflows, secrets, or published artifacts. It creates reports only.

## Run locally

```bash
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

The planner can be run safely with incomplete reports. The output explicitly describes missing inputs and never claims that missing data proves system health.
