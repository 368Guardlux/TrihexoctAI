# TrihexoctAI — TRIHEXΩ v2.0.0-alpha.5 — Read this first

This is the **complete TrihexoctAI / Guardlux TRIHEXΩ development project**, not a loose overlay. Extract the archive, open the single `TrihexoctAI` project folder, and upload the contents inside it to a development branch in the separate `368Guardlux/TrihexoctAI` repository. Do not upload this project into the original `368Guardlux/Trihexoct` repository. Preserve `.github/`, `config/`, `docs/`, `reports/`, `src/`, `tests/`, and `tools/`.

## Main additions in alpha.5

- Sixteen staged LLM review roles: twelve specialist analysts, three critics, and one synthesis guardian.
- Conservative candidate discovery from new exact third-party host rules in fresh, validated adblock-feed deltas.
- Curated publisher-group corroboration. Publisher labels are registry metadata, not proof of ownership or independence.
- Deterministic pre-screening for common functional services, shared hosting, and broad rule scope.
- Conditional HTTP caching, verified 304 reuse, SHA-256 cache integrity, bounded adaptive fetch concurrency, and source-health history.
- Per-feed drift screening that holds anomalous feed snapshots out of candidate discovery only; it does not change production feed coverage.
- Human-feedback learning ledger with append-only hash-chain integrity. Only confirmed after-trial human outcomes count as diagnostic labels.
- Learning-informed triage that adjusts review ordering only. It does not estimate threat probability or authorize blocking.
- Deterministic evolution planner that creates an evidence-based engineering backlog, tracks recurring issues, and never auto-resolves missing tasks.
- Operations Doctor, change-impact analyzer, rule provenance, controlled release gates, and split build/publish permissions.

## What “self-learning” means

The system learns operationally from explicit human adjudication and repeated machine-readable maintenance observations. It can improve diagnostic context and review prioritization. It does not train its own model weights, rewrite its own code, create trusted sources, alter policy thresholds, change filter rules, or publish without the existing independent release process.

## Important reality check

This is not AGI. Sixteen role-specific prompts to one configured language model are not sixteen independent minds. The model provider is optional and must be configured separately. The agents are read-only and advisory-only.

## Safe first steps

1. Back up your current stable v1.3.2 repository.
2. Upload this project to a separate development branch.
3. Install `requirements-ci.txt`.
4. Run `python tools/validate_trihexomega_pack.py`.
5. Run `python tools/validate_workflows.py`.
6. Run `python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json`.
7. Run `python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl`.
8. Run `python -m unittest discover -s tests -v`.
9. Inspect `TRIHEXOMEGA_V2_RELEASE_STATUS.md` and `UPLOAD_TO_GITHUB.md`.
10. Only then consider configuring an AI provider or running the live 32-feed maintenance cycle.

The package metadata is an offline bootstrap. It does not prove that all 32 live reference feeds were fetched when this archive was created. Brave compatibility and site functionality require real-browser testing.
