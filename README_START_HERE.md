# Start here — TRIHEXΩ v2.0.0-alpha.5

## Package identity

- Version: `2.0.0-alpha.5`
- Channel: development alpha / integration preview
- Source modules: 16, preserved byte-for-byte from v1.3.2
- Authored unique active rules: 833, unchanged
- Configured reference feeds: 32
- Advisory council: 16 bounded role calls (12 analysis, 3 critique, 1 synthesis)
- Maximum concurrent analysis calls: 8
- Maximum model calls per candidate batch: 16
- Maximum candidates per review batch: 8
- Maximum evidence items per candidate: 8
- Maximum agent timeout: 45 seconds
- Maximum response tokens per role: 1,400
- AI publication authority: none

## Validate before upload

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

To generate the deterministic engineering backlog from reports already present in `reports/`:

```bash
python tools/trihexomega/evolution_planner.py --reports-dir reports
```

## What runs automatically

The autonomous GitHub Actions workflow attempts a read-only maintenance, drift, discovery, learning-diagnostics, triage, optional swarm, and evolution-planning cycle twice daily. GitHub scheduled runs are best-effort and may be delayed. The workflow persists compact verified caches/state and uploads bounded reports; it does not publish rules.

The production build and publisher remain separate. The build/validation job is read-only; a separate publisher receives write permission only after validation and verifies the exact triggering commit and artifact checksum.

## Optional AI provider

Configure `TRIHEXOMEGA_AI_API_KEY` as an Actions secret and `TRIHEXOMEGA_AI_MODEL` as an Actions variable. Review provider data handling, retention, and cost before enabling. Without credentials/model, the deterministic maintenance cycle continues and AI review is skipped.

## Learning and evolution boundaries

Human-feedback outcomes are stored in a tamper-evident hash-chained ledger. Aggregate diagnostics can influence candidate review order. The evolution planner converts operational reports into an engineering backlog and tracks recurrence. Neither system changes rules, policies, source trust, model weights, permissions, or publication authority.

## Important limitations

There is no real AGI, no autonomous model-weight training, no autonomous code self-modification, and no automatic rule insertion. The 16 roles are specialist prompts to one configured LLM endpoint per run. Offline tests do not establish live availability of the 32 feeds, actual Brave parser compatibility, or zero website breakage.
