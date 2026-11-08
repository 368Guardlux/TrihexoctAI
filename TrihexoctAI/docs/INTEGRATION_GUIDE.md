# TRIHEXΩ v2.0.0-alpha.5 — Integration Guide

## Integration approach

Alpha.5 is an additive development release. It preserves all 16 production source modules and 833 authored active rules from the supplied v1.3.2 baseline. New maintenance, learning, intelligence, and evolution-planning components are integrated around the deterministic filter builder. The packaged filter list is an offline bootstrap.

## Safe branch strategy

1. Back up the current stable repository.
2. Create a separate development branch.
3. Upload the contents of the complete alpha.5 project folder to the repository root of that branch.
4. Preserve all files and the root layout; do not introduce an extra enclosing folder.
5. Run the local validation commands below.
6. Run GitHub Actions on the development branch and inspect artifacts.
7. Test representative pages in Brave and only then consider a controlled promotion.

## Local validation

```bash
python -m pip install --disable-pip-version-check --requirement requirements-ci.txt
python tools/validate_trihexomega_pack.py
python tools/validate_workflows.py
python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json
python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl
python -m unittest discover -s tests -v
python tools/audit_source_modules.py --output reports/source-inventory.json
python tools/build_filter.py --output /tmp/Trihexoct-alpha5-offline.txt --report /tmp/trihexoct-alpha5-offline-report.json
python tools/validate_filter.py /tmp/Trihexoct-alpha5-offline.txt
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

## Maintenance automation

The autonomous workflow performs read-only feed maintenance, drift analysis, discovery, feedback diagnostics, review triage, optional advisory review, and engineering backlog generation. It does not commit or publish rules. Its cache/state restoration and report artifacts are bounded; raw feed bodies are not uploaded.

## Optional LLM provider

AI review is disabled unless both `TRIHEXOMEGA_AI_API_KEY` and `TRIHEXOMEGA_AI_MODEL` are configured. Use a GitHub Actions secret for the API key and an Actions variable for the model. The endpoint must use HTTPS and support the expected OpenAI-compatible chat-completions JSON response. Review provider data handling and cost before activation. The swarm makes at most 16 role calls, uses one configured endpoint per run, and has no browser, shell, repository, secret, or publish tool access.

## Supervised learning

The feedback ledger accepts only human-maintainer review outcomes. It is append-only and hash-chained. Aggregate diagnostics may adjust review order but do not alter filtering rules, source trust, model weights, or release policy. The evolution planner prioritizes engineering tasks from reports and tracks recurrence without auto-closing tasks.

## Production workflow

The production workflow builds and validates with read-only repository permission. A separate publisher job receives write permission only after validation, checks the triggering commit and artifact integrity, and publishes approved outputs. Do not merge or promote alpha.5 until its live run and browser compatibility have been reviewed.
